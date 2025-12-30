import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path


class UTCFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = time.gmtime(record.created)
        if datefmt:
            return time.strftime(datefmt, ct) + "Z"
        return time.strftime("%Y-%m-%d %H:%M:%S", ct) + "Z"


def setup_logger(
    name: str = "",
    log_dir: str = "logs",
    level: int = logging.INFO,
    console_level: int | None = None,
) -> logging.Logger:
    """
    Configure and return a logger with file and console handlers.

    Args:
        name: Logger name (empty string for root logger)
        log_dir: Directory for log files
        level: Logging level for file handler
        console_level: Logging level for console (defaults to same as level)

    Returns:
        Configured logger
    """
    # Create log directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Monthly log file
    log_file = os.path.join(log_dir, f"{datetime.now(timezone.utc).strftime('%Y-%m')}.log")

    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
    logger.handlers.clear()  # Avoid duplicates on reload

    # Formatter
    formatter = UTCFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level or level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    for lib in [
        "telegram",
        "telegram.ext",
        "httpx",
        "httpcore",
        "apscheduler",
        "aiohttp",
    ]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logger
