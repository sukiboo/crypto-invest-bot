#!/usr/bin/env python3
"""Ad-hoc trigger for the first check_runway action in settings.yaml."""

import asyncio
import logging

from src.actions import ACTIONS, ActionContext
from src.kraken import KrakenClient, KrakenEarn, KrakenTrading
from src.notifications import TelegramNotifier
from src.utils import setup_logger
from src.utils.settings import Settings


async def main() -> None:
    setup_logger(level=logging.INFO)
    settings = Settings()
    await settings.validate()

    telegram = TelegramNotifier(
        bot_token=settings.env.telegram_bot_token,
        user_id=settings.env.telegram_user_id,
    )
    client = KrakenClient(
        api_key=settings.env.kraken_api_key,
        api_secret=settings.env.kraken_api_secret,
    )
    ctx = ActionContext(
        kraken_client=client,
        trading=KrakenTrading(client),
        earn=KrakenEarn(client),
        telegram=telegram,
        settings=settings,
    )

    runway = next((a for a in settings.actions if a.type == "check_runway"), None)
    if runway is None:
        raise SystemExit("No check_runway action in settings.yaml")

    try:
        original = telegram.send_alert

        async def echo(message: str, quiet: bool = False) -> bool:
            print(f"--- alert (quiet={quiet}) ---\n{message}\n---")
            return await original(message, quiet)

        telegram.send_alert = echo  # type: ignore[method-assign]
        await ACTIONS[runway.type].execute(runway, ctx)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
