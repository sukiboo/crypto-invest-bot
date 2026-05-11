from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.kraken import KrakenClient, KrakenEarn, KrakenTrading
from src.notifications import TelegramNotifier
from src.schemas import ActionConfig
from src.utils.settings import Settings


@dataclass
class ActionContext:
    kraken_client: KrakenClient
    trading: KrakenTrading
    earn: KrakenEarn
    telegram: TelegramNotifier
    settings: Settings


class Action(ABC):
    """An action returns a notification string to be sent via `send_update`,
    or None if it handled notifications itself (or has nothing to announce)."""

    @abstractmethod
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> str | None: ...
