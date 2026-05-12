#!/usr/bin/env python3
"""Debug: dump Earn/Strategies output."""

import asyncio
import json
import logging

from src.kraken import KrakenClient, KrakenEarn
from src.utils import setup_logger
from src.utils.settings import Settings


async def main() -> None:
    setup_logger(level=logging.INFO)
    settings = Settings()
    client = KrakenClient(
        api_key=settings.env.kraken_api_key,
        api_secret=settings.env.kraken_api_secret,
    )
    earn = KrakenEarn(client)
    try:
        unfiltered = await earn.get_strategies()
        print(f"Total strategies (unfiltered): {len(unfiltered)}")
        for s in unfiltered:
            print(
                f"  id={s.get('id')}  asset={s.get('asset')}  "
                f"lock_type={s.get('lock_type', {}).get('type')}"
            )
        for asset in ("USDC", "ETH", "SOL", "XBT"):
            items = await earn.get_strategies(asset)
            print(f"\nStrategies for {asset}: {len(items)}")
            for s in items:
                print(json.dumps(s, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
