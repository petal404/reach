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
    """Unfollows random users who are not in the database and do not follow back."""
    settings, _ = load_config()
    async with GithubAPI() as api:
        limit = settings['limits'].get('max_unfollow', 200)
        
        # Get my own username
        my_username = await api.get_authenticated_user()
        if not my_username:
            logger.error("Could not determine bot's own username. Aborting unfollow sequence.")
            return

        logger.info(f"Fetching users followed by {my_username} from GitHub...")
        all_following = await api.get_following(my_username)
        all_following_set = set(all_following)
        logger.info(f"Bot currently follows {len(all_following_set)} users.")

        logger.info("Fetching bot's current followers to identify who to exclude (those following back).")
        my_followers = await api.get_my_followers()
        my_followers_set = set(my_followers)
        logger.info(f"Bot has {len(my_followers_set)} followers.")

        logger.info("Fetching all usernames in database to exclude them from the unfollow list.")
        from .database import get_all_usernames_in_db
        usernames_in_db = get_all_usernames_in_db()
        logger.info(f"There are {len(usernames_in_db)} usernames in the database.")

        # Candidates for unfollowing are:
        # Those I follow who:
        # 1. Don't follow me back.
        # 2. Are not in the database.
        candidates = [user for user in all_following_set if user not in my_followers_set and user not in usernames_in_db]
        
        logger.info(f"Identified {len(candidates)} potential candidates for unfollowing (not in DB and not following back).")

        if not candidates:
            logger.info("No candidates for unfollowing found (either all follow back or all are in the database).")
            return

        # Pick random candidates up to the limit
        num_to_unfollow = min(len(candidates), limit)
        users_to_unfollow = random.sample(candidates, num_to_unfollow)

        logger.info(f"Starting unfollow sequence for {len(users_to_unfollow)} random users.")

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
