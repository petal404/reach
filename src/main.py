import argparse
import time
import random
import asyncio
import os
from .config_loader import load_config
from .database import initialize_database, get_user_stats
from .logger import setup_logger
from .scanner import scan_for_users
from .actions import follow_users, unfollow_users
from .metrics import metrics_tracker

# Import the dashboard app
from .dashboard.app import app as dashboard_app

LOCK_FILE = "reach.lock"

async def random_long_sleep(start_time, settings):
    """
    Puts the bot to sleep for a random duration after an initial operational period.
    Ensures the bot doesn't sleep in the first `min_sleep_minutes`.
    """
    logger = setup_logger()
    min_sleep_minutes = settings['delays'].get('long_sleep_min_minutes', 83)
    max_sleep_hours = settings['delays'].get('long_sleep_max_hours', 4)

    uptime_minutes = (time.time() - start_time) / 60
    if uptime_minutes < min_sleep_minutes:
        logger.info(f"Bot has been running for {uptime_minutes:.2f} minutes. Skipping long sleep as it's within the initial {min_sleep_minutes} minutes.")
        return

    max_sleep_seconds = int(max_sleep_hours * 60 * 60)
    min_sleep_seconds = 60 * 60
    if max_sleep_seconds < min_sleep_seconds:
        min_sleep_seconds = max_sleep_seconds

    sleep_duration_seconds = random.randint(min_sleep_seconds, max_sleep_seconds)

    logger.info(f"Bot has been running for {uptime_minutes:.2f} minutes. Entering random long sleep for {sleep_duration_seconds / 3600:.2f} hours.")
    await asyncio.sleep(sleep_duration_seconds)
    logger.info("Bot waking up from random long sleep.")

async def main():
    logger = setup_logger()
    
    if os.path.exists(LOCK_FILE):
        logger.info("Bot is already running. Exiting.")
        return

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

        logger.info("Bot starting...")
        start_time = time.time()
        initialize_database()
        settings, _ = load_config()

        parser = argparse.ArgumentParser(description="Reach GitHub Bot")
        parser.add_argument("--action", choices=['scan', 'follow', 'unfollow', 'all'], help="The action to perform.")
        parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making any changes.")
        parser.add_argument("--dashboard", action="store_true", help="Launch the monitoring dashboard.")
        args = parser.parse_args()

        if args.dashboard:
            logger.info("Launching dashboard...")
            # Flask app.run is synchronous, so it will block here.
            # It should be run in a separate process or thread if the bot is to run concurrently.
            # For now, it's a separate mode.
            dashboard_app.run(debug=True, port=5000) # You can change the port if needed
            return

        if not args.action:
            parser.error("argument --action is required unless --dashboard is used.")

        logger.info(f"Action: {args.action}, Dry Run: {args.dry_run}")

        if args.action in ['scan', 'all']:
            logger.info("Scanning for users...")
            await scan_for_users(dry_run=args.dry_run)

        if args.action in ['unfollow', 'all']:
            logger.info("Processing unfollows...")
            await unfollow_users(dry_run=args.dry_run)

        if args.action in ['follow', 'all']:
            logger.info("Processing follows...")
            await follow_users(dry_run=args.dry_run)

        logger.info("Bot run finished.")
        metrics_tracker.log_summary()
        await random_long_sleep(start_time, settings)
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)


if __name__ == "__main__":
    asyncio.run(main())