#!/usr/bin/env python3

import asyncio
import logging
import sys

from src import CryptoInvestBot, Settings
from src.utils import setup_logger


def main() -> int:
    setup_logger(level=logging.INFO)
    logger = logging.getLogger(__name__)
    try:
        settings = Settings()
        logger.info("Configuration loaded: %s", settings.bot_name)
        bot = CryptoInvestBot(settings)
        asyncio.run(bot.run())
        return 0
    except FileNotFoundError as e:
        logger.error("Configuration error: %s", e)
        return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
