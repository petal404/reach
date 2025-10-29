import logging
import asyncio
from datetime import datetime, timedelta, timezone
from .github_api import GithubAPI
from .database import add_or_update_user, is_user_disqualified
from .scoring import UserValidator
from .config_loader import load_config
from .metrics import metrics_tracker

logger = logging.getLogger(__name__)

def build_portfolio_search_query(criteria):
    """Builds the portfolio search query from keywords in the criteria file."""
    keywords = criteria.get('repository_keywords', ['portfolio'])
    
    # Join keywords with OR operator and group them with parentheses
    keyword_query_part = " OR ".join(f'"{keyword}"' for keyword in keywords)
    
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%d')
    max_followers = criteria.get('negative_signals', {}).get('max_followers', 100)
    
    # Construct the final query
    query = f'({keyword_query_part}) in:name,description,readme created:>={two_weeks_ago} followers:<={max_followers} sort:created-desc'
    
    logger.info(f"Built portfolio search query: {query}")
    return query

async def process_user(username, api, validator, already_followed_users, dry_run=False):
    """Process a single user: check if they should be disqualified and if not, schedule them for following."""
    metrics_tracker.users_processed += 1

    if username in already_followed_users:
        logger.info(f"User '{username}' is already being followed. Disqualifying.", extra={'props': {"username": username}})
        metrics_tracker.users_disqualified += 1
        if not dry_run:
            # We need user_data to disqualify, so we have to fetch it first.
            user_data = await api.get_user_details(username)
            if user_data:
                add_or_update_user(user_data, status='disqualified')
        return

    if is_user_disqualified(username):
        logger.debug(f"User '{username}' is already in the disqualified list. Skipping.", extra={'props': {"username": username}})
        return

    user_data = await api.get_user_details(username)
    if not user_data:
        logger.warning(f"Could not fetch details for user '{username}'. Skipping.", extra={'props': {"username": username}})
        return

    is_disqualified, reason = validator.is_disqualified(user_data)
    if is_disqualified:
        logger.info(f"User '{username}' was disqualified.", extra={'props': {"username": username, "reason": reason}})
        metrics_tracker.users_disqualified += 1
        if not dry_run:
            add_or_update_user(user_data, status='disqualified')
    else:
        logger.info(f"User '{username}' passed checks. Scheduling for following.", extra={'props': {"username": username}})
        metrics_tracker.users_scheduled += 1
        if not dry_run:
            add_or_update_user(user_data, status='targeted')

async def scan_for_users(dry_run=False):
    """Main async function to scan for users based on the new simplified criteria."""
    if dry_run:
        logger.info("DRY-RUN enabled. No database changes will be made.")

    settings, criteria = load_config()
    validator = UserValidator(criteria)
    
    found_users = set()
    already_followed_users = set()

    async with GithubAPI() as api:
        # Get the authenticated user's username
        auth_user = await api.get_authenticated_user()
        if auth_user:
            logger.info(f"Authenticated as {auth_user}. Fetching list of users already being followed.")
            already_followed_users = set(await api.get_following(auth_user))
            logger.info(f"Found {len(already_followed_users)} users that are already being followed.")

        # Task 1: Portfolio Creators
        logger.info("Searching for users who recently created portfolio repositories...")
        portfolio_query = build_portfolio_search_query(criteria)
        repo_search_results = await api.search_repositories(portfolio_query, limit=100)
        if repo_search_results:
            for repo in repo_search_results:
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

        if not found_users:
            logger.info("Scan complete: No potential users found in this run.")
            return

        logger.info(f"[SCAN COMPLETE] Found a total of {len(found_users)} unique potential users to process.")

        # Process all found users
        tasks = [process_user(username, api, validator, already_followed_users, dry_run) for username in found_users]
        await asyncio.gather(*tasks)
