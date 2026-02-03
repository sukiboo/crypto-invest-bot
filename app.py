#!/usr/bin/env python3

import asyncio
import logging
import sys

from src import CryptoInvestBot, Settings
from src.notifications import TelegramNotifier
from src.schemas import EnvSettings
from src.utils import setup_logger

logger = logging.getLogger(__name__)


async def async_main() -> None:
    env = EnvSettings()  # pyright: ignore[reportCallIssue]
    notifier = TelegramNotifier(env.telegram_bot_token, env.telegram_user_id)

    try:
        settings = Settings()
        await settings.validate()
        logger.info("Configuration validated: %s", settings.bot_name)
        bot = CryptoInvestBot(settings)
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        await notifier.send_alert(f"Bot crashed: {e}")
        raise


def main() -> int:
    setup_logger(level=logging.INFO)
    try:
        asyncio.run(async_main())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
