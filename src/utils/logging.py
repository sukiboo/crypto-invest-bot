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
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now(timezone.utc).strftime('%Y-%m')}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # capture all; handlers filter
    logger.handlers.clear()

    formatter = UTCFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level or level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    for lib in ("telegram", "telegram.ext", "httpx", "httpcore", "apscheduler", "aiohttp"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logger
