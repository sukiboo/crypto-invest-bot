"""Main bot orchestrating all components."""

import asyncio
import logging
import signal
from typing import Any

from src.schemas import ActionConfig
from src.utils.settings import Settings
from src.kraken import KrakenClient, KrakenEarn, KrakenTrading
from src.notifications import TelegramNotifier
from src.scheduler import JobScheduler

logger = logging.getLogger(__name__)


class CryptoInvestBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._shutdown_event = asyncio.Event()

        # Initialize components
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
        """Execute a scheduled action."""
        result: dict[str, Any] = {"action": action.name, "type": action.type, "success": False}

        try:
            logger.info("Executing action: %s [%s]", action.name, action.type)

            if action.type == "order":
                result["data"] = await self._execute_order(action)
                details = f"{action.side} ${action.amount} on {action.pair}"
            elif action.type == "earn":
                result["data"] = await self._execute_earn(action)
                amount_str = f"{action.amount}" if action.amount else "all"
                details = f"{action.strategy} {amount_str} {action.asset}"
            else:
                raise ValueError(f"Unknown action type: {action.type}")

            result["success"] = True
            await self.telegram.send_update(title=f"{action.name}", details=details)

        except Exception as e:
            logger.exception("Action '%s' failed: %s", action.name, e)
            result["error"] = str(e)
            await self.telegram.send_alert(title=f"{action.name} failed", details=str(e))

        return result

    async def _execute_order(self, action: ActionConfig) -> dict[str, Any]:
        """Execute a trading order."""
        assert action.pair is not None
        assert action.amount is not None

        if action.order_type == "market":
            return await self.trading.place_market_order(
                pair=action.pair,
                side=action.side,
                amount=action.amount,
            )
        raise ValueError(f"Unsupported order type: {action.order_type}")

    async def _execute_earn(self, action: ActionConfig) -> dict[str, Any] | None:
        """Execute an earn/staking action."""
        assert action.asset is not None

        return await self.earn.stake_after_purchase(
            asset=action.asset,
            amount=action.amount,  # None = stake all available
            strategy_type=action.strategy,
        )

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown handlers."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)

    async def start(self) -> None:
        """Start the bot and schedule all actions."""
        logger.info("Starting %s...", self.settings.bot_name)

        # Schedule all actions
        for action in self.settings.actions:
            self.scheduler.add_action(action, self.execute_action)

        # Start the scheduler
        self.scheduler.start()

        # Log next run times
        next_runs = self.scheduler.get_next_run_times()
        schedule_info = "\n".join(f"  - {name}: {time}" for name, time in next_runs.items())
        logger.info("Scheduled actions:\n%s", schedule_info)

        # Send startup notification
        await self.telegram.send_update(
            title=f"{self.settings.bot_name} started",
            details=f"Monitoring {len(self.settings.actions)} action(s)",
        )

    async def run(self) -> None:
        """Run the bot until shutdown signal."""
        self._setup_signal_handlers()
        await self.start()

        # Wait for shutdown signal
        logger.info("Bot running. Press Ctrl+C to stop.")
        await self._shutdown_event.wait()

        await self.stop()

    async def stop(self) -> None:
        """Stop the bot and cleanup resources."""
        logger.info("Shutting down %s...", self.settings.bot_name)

        self.scheduler.shutdown(wait=True)
        await self.kraken_client.close()

        await self.telegram.send_update(
            title=f"{self.settings.bot_name} stopped",
            details="Graceful shutdown complete",
        )

        logger.info("Shutdown complete")
