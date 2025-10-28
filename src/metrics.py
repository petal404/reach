import time
import logging

logger = logging.getLogger(__name__)

class BotMetrics:
    def __init__(self):
        self.start_time = time.time()
        self.api_requests = 0
        self.errors = 0
        self.total_sleep_time = 0
        self.users_processed = 0
        self.users_disqualified = 0
        self.users_scheduled = 0
        self.users_followed = 0
        self.users_unfollowed = 0

    def increment_api_requests(self):
        self.api_requests += 1

    def increment_errors(self):
        self.errors += 1

    def add_sleep_time(self, duration):
        self.total_sleep_time += duration

    def log_summary(self):
        """Logs a comprehensive summary of the bot's run."""
        hit_rate = (self.users_scheduled / self.users_processed * 100) if self.users_processed > 0 else 0
        total_runtime = time.time() - self.start_time

        # Format total_sleep_time
        sleep_td = timedelta(seconds=self.total_sleep_time)
        hours, remainder = divmod(sleep_td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = sleep_td.microseconds // 1000
        formatted_sleep_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

        summary = (
            "\n---SUMMARY---"
            f"Total users processed: {self.users_processed}\n" +
            f"Total Disqualified: {self.users_disqualified}\n" +
            f"Total Scheduled for follow: {self.users_scheduled}\n" +
            f"Percentage Hit rate: {hit_rate:.2f}%\n" +
            f"Total Followed in run: {self.users_followed}\n" +
            f"Total Unfollowed in run: {self.users_unfollowed}\n" +
            f"Total users resulting to errors: {self.errors}\n" +
            f"Total number of API requests sent: {self.api_requests}\n" +
            f"Total sleeping time: {formatted_sleep_time}\n" +
            f"Total runtime: {timedelta(seconds=total_runtime)}\n"
        )
        logger.info(summary)

# Global metrics instance
metrics_tracker = BotMetrics()
