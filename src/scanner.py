import logging
import asyncio
from datetime import datetime, timedelta, timezone
from .github_api import GithubAPI
from .database import add_or_update_user, is_user_disqualified, get_repo_last_scanned_at, update_repo_last_scanned_at
from .scoring import UserValidator
from .config_loader import load_config
from .metrics import metrics_tracker

logger = logging.getLogger(__name__)

async def process_user(username, api, validator, dry_run=False):
    """Process a single user: check if they should be disqualified and if not, schedule them for following.
    Returns True if the user was scheduled, False otherwise.
    """
    metrics_tracker.users_processed += 1

    # Check local database for previous disqualification
    if is_user_disqualified(username):
        logger.debug(f"User '{username}' is already in the disqualified list. Skipping.", extra={'props': {"username": username}})
        return False

    user_data = await api.get_user_details(username)
    if not user_data:
        logger.warning(f"Could not fetch details for user '{username}'. Skipping.", extra={'props': {"username": username}})
        return False

    is_disqualified, reason = validator.is_disqualified(user_data)
    if is_disqualified:
        logger.info(f"User '{username}' was disqualified.", extra={'props': {"username": username, "reason": reason}})
        metrics_tracker.users_disqualified += 1
        if not dry_run:
            add_or_update_user(user_data, status='disqualified')
        return False
    else:
        logger.info(f"User '{username}' passed checks. Scheduling for following.", extra={'props': {"username": username}})
        metrics_tracker.users_scheduled += 1
        if not dry_run:
            add_or_update_user(user_data, status='targeted')
        return True

async def scan_for_users(dry_run=False):
    """Main async function to scan for users based on the new simplified criteria."""
    if dry_run:
        logger.info("DRY-RUN enabled. No database changes will be made.")

    settings, criteria = load_config()
    validator = UserValidator(criteria)
    # Get the max follow limit to cap scheduling
    max_follows_per_run = settings.get('limits', {}).get('max_follow', 350)
    
    found_users = set()
    already_followed_users = set()

    async with GithubAPI() as api:
        # Get the authenticated user's username
        auth_user = await api.get_authenticated_user()
        if auth_user:
            logger.info(f"Authenticated as {auth_user}. Fetching list of users already being followed.")
            # We fetch these to filter them out from search results immediately
            already_followed_users = set(await api.get_following(auth_user))
            logger.info(f"Found {len(already_followed_users)} users that are already being followed.")

        # Task 1: Keyword-based search
        logger.info("Searching for users based on keywords...")
        keywords = criteria.get('repository_keywords', ['portfolio'])
        search_tasks = []
        two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%d')
        max_followers = criteria.get('negative_signals', {}).get('max_followers', 100)

        for keyword in keywords:
            query = f'{keyword} in:name,description,readme created:>={two_weeks_ago} followers:<={max_followers} sort:created-desc'
            logger.info(f"Built search query: {query}")
            for page in range(1, 6):
                search_tasks.append(api.search_repositories(query, limit=100, page=page))
        
        search_results = await asyncio.gather(*search_tasks)
        for result in search_results:
            if result:
                for repo in result:
                    owner = repo.get('owner')
                    if owner and owner.get('type') == 'User':
                        found_users.add(owner['login'])

        # Task 2: Star/Fork Activity
        logger.info("Searching for users who recently starred or forked repositories...")
        public_events = await api.get_public_events()
        if public_events:
            fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
            for event in public_events:
                event_time = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                if event['type'] in ['WatchEvent', 'ForkEvent'] and event_time > fourteen_days_ago:
                    actor = event.get('actor')
                    if actor:
                        found_users.add(actor['login'])

        # Task 3: High-Signal Repo Watcher
        logger.info("Task 3: Checking for new stars on high-signal learning repositories...")
        target_repos = criteria.get('target_repos', [])
        for repo_full_name in target_repos:
            try:
                owner, repo_name = repo_full_name.split('/')
                last_scanned = get_repo_last_scanned_at(repo_full_name)
                
                # Default to 24 hours ago if never scanned, to avoid mass-processing old stars
                if not last_scanned:
                    last_scanned = datetime.now(timezone.utc) - timedelta(hours=24)
                    logger.info(f"First time scanning {repo_full_name}. Defaulting to events since {last_scanned}.")
                else:
                    logger.info(f"Scanning {repo_full_name} for stars since {last_scanned}.")

                events = await api.get_repo_events(owner, repo_name, limit=100)
                if not events:
                    continue

                newest_event_time = last_scanned
                new_stars_found = 0

                for event in events:
                    if event['type'] == 'WatchEvent':
                        event_time = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                        
                        # Keep track of the newest event time to update the DB
                        if event_time > newest_event_time:
                            newest_event_time = event_time

                        if event_time > last_scanned:
                            actor = event.get('actor')
                            if actor:
                                found_users.add(actor['login'])
                                new_stars_found += 1
                
                if new_stars_found > 0:
                    logger.info(f"Found {new_stars_found} new stars on {repo_full_name}.")
                
                # Update state to the timestamp of the newest event we saw (or kept same if no new events)
                # We add a tiny buffer (1 second) to avoid duplicate processing of the exact same timestamp
                if newest_event_time > last_scanned:
                    update_repo_last_scanned_at(repo_full_name, newest_event_time)

            except Exception as e:
                logger.error(f"Error scanning repo {repo_full_name}: {e}")

        if not found_users:
            logger.info("Scan complete: No potential users found in this run.")
            return

        # NEW: Filter out already followed users strategically BEFORE processing
        original_count = len(found_users)
        found_users = {u for u in found_users if u not in already_followed_users}
        skipped_count = original_count - len(found_users)
        
        if skipped_count > 0:
            logger.info(f"Strategically skipped {skipped_count} users who are already being followed to save API calls.")

        logger.info(f"[SCAN COMPLETE] Found a total of {len(found_users)} unique potential users to process.")
        logger.info(f"Processing users with a limit of {max_follows_per_run} scheduled follows for this run.")

        # Process found users until we hit the max_follows_per_run limit
        scheduled_count = 0
        for username in found_users:
            if scheduled_count >= max_follows_per_run:
                logger.info(f"Reached scheduling limit of {max_follows_per_run} users. Stopping scan processing.")
                break
            
            # Process users sequentially to respect the limit
            # Note: sequential processing is safer for strict limits but slower. 
            # Given we want to stop exactly at the limit and save API calls, this is preferred over gather().
            is_scheduled = await process_user(username, api, validator, dry_run)
            if is_scheduled:
                scheduled_count += 1
