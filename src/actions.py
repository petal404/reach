import logging
import asyncio
import random
from datetime import datetime, timedelta, timezone
from .github_api import GithubAPI
from .database import update_user_status, get_users_to_check, count_followed_users, get_users_by_status_and_score, get_followed_users
from .config_loader import load_config
from .metrics import metrics_tracker
from .scoring import UserValidator

logger = logging.getLogger(__name__)

async def follow_users(dry_run=False):
    """Follows a batch of users from the database based on the new stealth criteria."""
    settings, _ = load_config()
    max_follow_per_run = settings['limits'].get('max_follow', 350)
    
    users_to_follow = get_users_by_status_and_score('targeted', min_score=0, limit=max_follow_per_run)

    if not users_to_follow:
        logger.info("No users scheduled for following in this run.")
        return

    logger.info(f"Starting follow sequence for {len(users_to_follow)} targeted users.")

    followed_today_count = 0
    user_index = 0
    
    async with GithubAPI() as api:
        while user_index < len(users_to_follow) and followed_today_count < max_follow_per_run:
            batch_size = random.randint(13, 33)
            
            # Determine the actual size of the current batch
            end_index = min(user_index + batch_size, len(users_to_follow))
            batch_users = users_to_follow[user_index:end_index]
            
            # Log the batch in the desired format
            usernames_in_batch = [user['username'] for user in batch_users]
            logger.info(f'batch of {len(usernames_in_batch)}: {", ".join(usernames_in_batch)}')

            for user_dict in batch_users:
                if followed_today_count >= max_follow_per_run:
                    logger.info(f"Daily follow limit of {max_follow_per_run} reached.")
                    break

                username = user_dict['username']
                
                if dry_run:
                    logger.info(f"[DRY-RUN] Would follow user: {username}", extra={'props': {"username": username, "dry_run": True}})
                    update_user_status(username, 'skipped')
                    followed_today_count += 1
                    continue

                success = await api.follow_user(username)
                if success:
                    logger.info(f"Successfully followed user: {username}", extra={'props': {"username": username}})
                    update_user_status(username, 'followed')
                    metrics_tracker.users_followed += 1
                    followed_today_count += 1
                else:
                    logger.error(f"Failed to follow user: {username}", extra={'props': {"username": username}})
                    update_user_status(username, 'skipped')

            user_index += len(batch_users)

            if followed_today_count >= max_follow_per_run:
                break

            # Exponential backoff after 98 follows
            if followed_today_count > 98:
                sleep_min = settings['delays'].get('action_min', 10) * (followed_today_count / 10)
                sleep_max = settings['delays'].get('action_max', 90) * (followed_today_count / 10)
            else:
                sleep_min = 10  # 10 seconds
                sleep_max = 90 # 1.5 minutes
            
            sleep_duration = random.randint(int(sleep_min), int(sleep_max))
            logger.info(f"Batch complete. Pausing for {sleep_duration} seconds.")
            await asyncio.sleep(sleep_duration)

async def unfollow_users(dry_run=False):
    """Unfollows users who are not following back or have become disqualified, prioritizing the oldest non-followers."""
    settings, criteria = load_config()
    validator = UserValidator(criteria)
    async with GithubAPI() as api:
        limit = settings['limits'].get('max_unfollow', 200)
        
        logger.info("Fetching bot's current followers to identify non-followers efficiently.")
        my_followers = await api.get_my_followers()
        my_followers_set = set(my_followers)
        logger.info(f"Bot has {len(my_followers_set)} followers.")

        # Get all followed users from DB
        followed_users = get_followed_users()
        # Sort by followed_at ASC (oldest first)
        # Handle cases where followed_at might be None (though it shouldn't be for 'followed' status)
        followed_users.sort(key=lambda x: x['followed_at'] if x['followed_at'] else datetime.min.replace(tzinfo=timezone.utc))

        users_to_unfollow = []

        # 1. Identify users who are not following back
        for user_dict in followed_users:
            username = user_dict['username']
            if username not in my_followers_set:
                users_to_unfollow.append(username)
                if len(users_to_unfollow) >= limit:
                    break
        
        logger.info(f"Identified {len(users_to_unfollow)} users who haven't followed back.")

        # 2. If we still have room, check for disqualified users among those who DO follow back (optional, but keeping for completeness)
        if len(users_to_unfollow) < limit:
            remaining_limit = limit - len(users_to_unfollow)
            logger.info(f"Checking for disqualified users among those who follow back (up to {remaining_limit} more).")
            # We check the oldest ones who follow back
            checked_count = 0
            for user_dict in followed_users:
                username = user_dict['username']
                if username in my_followers_set:
                    # To conserve resources, we only check a few or skip this if not strictly required
                    # But the previous implementation had it. Let's limit it to avoid too many API calls.
                    if checked_count >= remaining_limit * 2: # Check twice as many as we need to find
                        break
                    
                    user_data = await api.get_user_details(username)
                    checked_count += 1
                    if user_data:
                        is_disqualified, reason = validator.is_disqualified(user_data)
                        if is_disqualified:
                            logger.info(f"Followed user {username} is now disqualified (Reason: {reason}). Scheduling for unfollow.")
                            if username not in users_to_unfollow:
                                users_to_unfollow.append(username)
                                if len(users_to_unfollow) >= limit:
                                    break

        if not users_to_unfollow:
            logger.info("No users to unfollow at this time.")
            return

        logger.info(f"Starting unfollow sequence for {len(users_to_unfollow)} users.")

        unfollowed_count = 0
        for username in users_to_unfollow:
            if dry_run:
                logger.info(f"[DRY-RUN] Would unfollow user: {username}", extra={'props': {"username": username, "dry_run": True}})
                unfollowed_count += 1
                continue

            success = await api.unfollow_user(username)
            if success:
                logger.info(f"Successfully unfollowed user: {username}", extra={'props': {"username": username}})
                update_user_status(username, 'unfollowed')
                metrics_tracker.users_unfollowed += 1
                unfollowed_count += 1
            else:
                logger.error(f"Failed to unfollow user: {username}", extra={'props': {"username": username}})

            # Use shorter interval for unfollowing to speed up 200 unfollows, but still be safe
            sleep_duration = random.randint(2, 8) 
            await asyncio.sleep(sleep_duration)

        logger.info(f"Unfollow sequence complete. Total unfollowed: {unfollowed_count}")
