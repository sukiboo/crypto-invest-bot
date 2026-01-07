"""Main bot orchestrating all components."""

import asyncio
import logging
import signal
from typing import Any

from src.kraken import KrakenClient, KrakenEarn, KrakenTrading
from src.notifications import TelegramNotifier
from src.scheduler import JobScheduler
from src.schemas import ActionConfig
from src.utils.settings import Settings

logger = logging.getLogger(__name__)


class CryptoInvestBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._shutdown_event = asyncio.Event()

        self.telegram = TelegramNotifier(
            bot_token=settings.env.telegram_bot_token,
            user_id=settings.env.telegram_user_id,
        )

        self.kraken_client = KrakenClient(
            api_key=settings.env.kraken_api_key,
            api_secret=settings.env.kraken_api_secret,
        )
        self.trading = KrakenTrading(self.kraken_client)
        self.earn = KrakenEarn(self.kraken_client)

        self.scheduler = JobScheduler()

    async def execute_action(self, action: ActionConfig) -> dict[str, Any]:
        result: dict[str, Any] = {"action": action.name, "type": action.type, "success": False}

        try:
            logger.info("Executing action: %s [%s]", action.name, action.type)

            if action.type == "order":
                result["data"] = await self._execute_order(action)
                details = await self._format_order_details(action, result["data"])
            elif action.type == "earn":
                result["data"] = await self._execute_earn(action)
                amount_str = f"{action.amount}" if action.amount else "all"
                details = f"{action.strategy} {amount_str} {action.asset}"
            else:
                raise ValueError(f"Unknown action type: {action.type}")

            result["success"] = True
            await self.telegram.send_update(f"{action.name}: {details}")

        except Exception as e:
            logger.exception("Action '%s' failed: %s", action.name, e)
            result["error"] = str(e)
            await self.telegram.send_alert(f"{action.name}: {e}")

        return result

    async def _execute_order(self, action: ActionConfig) -> dict[str, Any]:
        assert action.pair is not None
        assert action.amount is not None

        if action.order_type == "market":
            return await self.trading.place_market_order(
                pair=action.pair,
                side=action.side,
                amount=action.amount,
            )
        raise ValueError(f"Unsupported order type: {action.order_type}")

    async def _format_order_details(
        self, action: ActionConfig, order_result: dict[str, Any]
    ) -> str:
        """Format order details for notification, including purchased amount."""
        try:
            txids = order_result.get("txid", [])
            order_details = await self.trading.query_orders(txids[0])
            order_info = order_details.get(txids[0], {})
            # vol_exec is the amount of base currency bought/sold
            vol_exec = order_info.get("vol_exec", "??")
            # price_avg is the average execution price
            price_avg = float(order_info.get("price", "0"))
            # format: "buy 0.1 of XETHZUSD for $300.00 @ $3000.00"
            return (
                f"{action.side} {vol_exec} of {action.pair} "
                f"for ${action.amount:.2f} @ ${price_avg:.2f}"
            )
        except Exception as e:
            logger.warning("Could not fetch order details: %s", e)
            return f"{action.side} ${action.amount:.2f} of {action.pair}"

    async def _execute_earn(self, action: ActionConfig) -> dict[str, Any] | None:
        assert action.asset is not None

        return await self.earn.stake_after_purchase(
            asset=action.asset,
            amount=action.amount,  # None = stake all available
            strategy_type=action.strategy,
        )

    def _setup_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)

    async def start(self) -> None:
        logger.info("Starting %s...", self.settings.bot_name)

        for action in self.settings.actions:
            self.scheduler.add_action(action, self.execute_action)

        self.scheduler.start()
        next_runs = self.scheduler.get_next_run_times()
        schedule_info = "\n".join(f"  - {name}: {time}" for name, time in next_runs.items())
        logger.info("Scheduled actions:\n%s", schedule_info)

        await self.telegram.send_info(
            f"{self.settings.bot_name} started with {len(self.settings.actions)} actions"
        )

    async def run(self) -> None:
        self._setup_signal_handlers()
        await self.start()

        logger.info("Bot running. Press Ctrl+C to stop.")
        await self._shutdown_event.wait()

        await self.stop()

    async def stop(self) -> None:
        logger.info("Shutting down %s...", self.settings.bot_name)

        self.scheduler.shutdown(wait=True)
        await self.kraken_client.close()

        await self.telegram.send_update(f"{self.settings.bot_name} stopped")

        logger.info("Shutdown complete")
