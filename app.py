#!/usr/bin/env python3

import asyncio
import logging
import sys

from src import CryptoInvestBot, Settings
from src.utils import setup_logger

logger = logging.getLogger(__name__)


async def async_main() -> None:
    settings = Settings()
    await settings.validate()
    logger.info("Configuration validated: %s", settings.bot_name)
    bot = CryptoInvestBot(settings)
    await bot.run()


def main() -> int:
    setup_logger(level=logging.INFO)
    try:
        asyncio.run(async_main())
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
