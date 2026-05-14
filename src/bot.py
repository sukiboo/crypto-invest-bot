import asyncio
import logging
import signal

from src.actions import ACTIONS, ActionContext
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

        self.ctx = ActionContext(
            kraken_client=self.kraken_client,
            trading=self.trading,
            earn=self.earn,
            telegram=self.telegram,
            settings=settings,
        )

    async def execute_action(self, config: ActionConfig) -> None:
        try:
            logger.info("Executing action: %s [%s]", config.name, config.type)
            details = await ACTIONS[config.type].execute(config, self.ctx)
            if details is not None:
                await self.telegram.send_update(f"{config.name}: {details}")
        except Exception as e:
            logger.exception("Action '%s' failed: %s", config.name, e)
            await self.telegram.send_alert(f"{config.name}: {e}")

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

        self.scheduler.shutdown(wait=False)
        await self.kraken_client.close()

        await self.telegram.send_info(f"{self.settings.bot_name} stopped")

        logger.info("Shutdown complete")
