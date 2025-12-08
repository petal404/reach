import logging
import sys
from pythonjsonlogger import jsonlogger

class SummaryFilter(logging.Filter):
    def filter(self, record):
        return getattr(record, 'is_summary', False)

def setup_logger():
    """Set up the logger for structured JSON output."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler for JSON logs - Only for summaries
    log_handler = logging.FileHandler("reach.log")
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    log_handler.setFormatter(formatter)
    log_handler.addFilter(SummaryFilter())
    logger.addHandler(log_handler)

    # Console handler for human-readable logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger