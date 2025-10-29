import logging
import asyncio
import random
from datetime import datetime, timedelta, timezone
from .github_api import GithubAPI
from .database import update_user_status, get_followed_users, get_users_by_status_and_score
from .config_loader import load_config
from .metrics import metrics_tracker
from .scoring import UserValidator

logger = logging.getLogger(__name__)

async def follow_users(dry_run=False):
    """Follows a batch of users from the database based on the new stealth criteria."""
    settings, _ = load_config()
    max_follow_per_run = settings['limits'].get('max_follow', 350)
    followed_today_count = 0

    # Get all users scheduled for following
    users_to_follow = get_users_by_status_and_score('targeted', min_score=0, limit=max_follow_per_run)

    if not users_to_follow:
        logger.info("No users scheduled for following in this run.")
        return

    logger.info(f"Starting follow sequence for {len(users_to_follow)} targeted users.")

    async with GithubAPI() as api:
        for user_dict in users_to_follow:
            if followed_today_count >= max_follow_per_run:
                logger.info(f"Daily follow limit of {max_follow_per_run} reached. Remaining users will be processed in the next run.")
                break

            username = user_dict['username']
            
            # Perform a random number of follows (4-11) before pausing
            batch_size = random.randint(4, 11)
            logger.info(f"Processing a batch of up to {batch_size} users.")

            for i in range(batch_size):
                if followed_today_count >= max_follow_per_run:
                    break
                
                # This logic needs to be improved to get the next user from the list
                # For now, we will just process the current user and then break the inner loop
                if i > 0:
                    break

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

            # Exponential backoff after 98 follows
            if followed_today_count > 98:
                sleep_min = settings['delays'].get('action_min', 10) * (followed_today_count / 10)
                sleep_max = settings['delays'].get('action_max', 90) * (followed_today_count / 10)
            else:
                sleep_min = 10  # 10 seconds
                sleep_max = 900 # 15 minutes
            
            sleep_duration = random.randint(int(sleep_min), int(sleep_max))
            logger.info(f"Batch complete. Pausing for {sleep_duration} seconds.")
            await asyncio.sleep(sleep_duration)

async def unfollow_users(dry_run=False):
    """Unfollows users who are not following back or have become disqualified."""
    settings, criteria = load_config()
    validator = UserValidator(criteria)
    async with GithubAPI() as api:
        limit = settings['limits'].get('max_unfollow', 50)
        inactive_days_threshold = settings['unfollow'].get('inactive_days', 270)
        
        # 1. Get users who don't follow back
        followed_users = get_followed_users()
        users_to_unfollow = set()

        for user_dict in followed_users:
            username = user_dict['username']
            followed_at = user_dict.get('followed_at')

            is_follower = await api.check_is_follower(username)
            if not is_follower:
                if followed_at and (datetime.now(timezone.utc) - followed_at).days > inactive_days_threshold:
                    logger.info(f"User {username} has not followed back for >{inactive_days_threshold} days. Scheduling for unfollow.")
                    users_to_unfollow.add(username)

        # 2. Get followed users who are now disqualified
        for user_dict in followed_users:
            username = user_dict['username']
            user_data = await api.get_user_details(username)
            if user_data:
                is_disqualified, reason = validator.is_disqualified(user_data)
                if is_disqualified:
                    logger.info(f"Followed user {username} is now disqualified. Reason: {reason}. Scheduling for unfollow.")
                    users_to_unfollow.add(username)

        if not users_to_unfollow:
            logger.info("No users to unfollow at this time.")
            return

        logger.info(f"Found {len(users_to_unfollow)} users to unfollow. Processing up to {limit} users.")

        for username in list(users_to_unfollow)[:limit]:
            if dry_run:
                logger.info(f"[DRY-RUN] Would unfollow user: {username}", extra={'props': {"username": username, "dry_run": True}})
                # In a real dry run, we might change status to 'skipped' but here we do nothing to avoid altering the DB state for the next step
                continue

            success = await api.unfollow_user(username)
            if success:
                logger.info(f"Successfully unfollowed user: {username}", extra={'props': {"username": username}})
                update_user_status(username, 'unfollowed') # This will now delete the user
                metrics_tracker.users_unfollowed += 1
            else:
                logger.error(f"Failed to unfollow user: {username}", extra={'props': {"username": username}})

            # Use shorter, 1/3rd interval for unfollowing
            sleep_duration = random.randint(3, 30)
            logger.debug(f"Sleeping for {sleep_duration} seconds...", extra={'props': {"sleep_duration": sleep_duration}})
            await asyncio.sleep(sleep_duration)
