from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PAIR_PATTERN = re.compile(r"^[A-Z0-9]{5,12}$")
ASSET_PATTERN = re.compile(r"^[A-Z0-9]{2,6}$")
from pydantic_settings import BaseSettings, SettingsConfigDict

ActionType = Literal["order", "earn", "check_runway", "maintain_reserve"]
OrderType = Literal["market", "limit"]
OrderSide = Literal["buy", "sell"]
EarnLockType = Literal["flexible", "bonded", "restaked"]


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore extra env vars
    )
    kraken_api_key: str
    kraken_api_secret: str
    telegram_bot_token: str
    telegram_user_id: str


class ActionConfig(BaseModel):
    name: str
    type: ActionType
    schedule: str  # cron expression

    # For order actions
    pair: str | None = None  # exact Kraken trading pair, e.g. "XETHZUSD"
    order_type: OrderType = "market"
    side: OrderSide = "buy"

    # For earn actions
    asset: str | None = None  # exact Kraken asset name, e.g. "ETH", "XBT"
    strategy: EarnLockType | None = None

    # For check_runway actions
    days: int | None = None  # lookahead horizon in days

    # Shared (required for order, optional for earn)
    amount: float | None = None  # None for earn = stake all available

    @model_validator(mode="after")
    def validate_action_fields(self) -> "ActionConfig":
        if self.type == "order":
            if not self.pair:
                raise ValueError(f"Action '{self.name}': 'pair' is required for order actions")
            if not PAIR_PATTERN.match(self.pair):
                raise ValueError(f"Action '{self.name}': invalid pair format '{self.pair}'")
            if self.amount is None:
                if self.side != "buy":
                    raise ValueError(
                        f"Action '{self.name}': 'amount=None' is only supported for buy orders"
                    )
            elif self.amount <= 0:
                raise ValueError(f"Action '{self.name}': 'amount' must be positive if specified")
        elif self.type == "earn":
            if not self.asset:
                raise ValueError(f"Action '{self.name}': 'asset' is required for earn actions")
            if not ASSET_PATTERN.match(self.asset):
                raise ValueError(f"Action '{self.name}': invalid asset format '{self.asset}'")
            if not self.strategy:
                raise ValueError(f"Action '{self.name}': 'strategy' is required for earn actions")
            if self.amount is not None and self.amount <= 0:
                raise ValueError(f"Action '{self.name}': 'amount' must be positive if specified")
        elif self.type == "check_runway":
            if not self.days or self.days <= 0:
                raise ValueError(
                    f"Action '{self.name}': 'days' must be positive for check_runway actions"
                )
        elif self.type == "maintain_reserve":
            if not self.asset:
                raise ValueError(
                    f"Action '{self.name}': 'asset' is required for maintain_reserve actions"
                )
            if not ASSET_PATTERN.match(self.asset):
                raise ValueError(f"Action '{self.name}': invalid asset format '{self.asset}'")
            if not self.strategy:
                raise ValueError(
                    f"Action '{self.name}': 'strategy' is required for maintain_reserve actions"
                )
            if not self.days or self.days <= 0:
                raise ValueError(
                    f"Action '{self.name}': 'days' must be positive for maintain_reserve actions"
                )
        return self


class AppConfig(BaseModel):
    bot_name: str = "crypto-invest-bot"
    actions: list[ActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def handle_none_actions(cls, data: dict) -> dict:
        if data.get("actions") is None:
            data["actions"] = []
        return data
