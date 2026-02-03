from pathlib import Path

import yaml

from src.kraken.client import KrakenClient
from src.kraken.earn import KrakenEarn
from src.schemas import ActionConfig, AppConfig, EnvSettings


class Settings:
    def __init__(self, config_path: str | Path = "settings.yaml") -> None:
        self.env = EnvSettings()  # pyright: ignore[reportCallIssue]
        self.app = self._load_yaml_config(config_path)

    def _load_yaml_config(self, config_path: str | Path) -> AppConfig:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return AppConfig(**data)

    @property
    def bot_name(self) -> str:
        return self.app.bot_name

    @property
    def actions(self) -> list[ActionConfig]:
        return self.app.actions

    async def validate(self) -> None:
        client = KrakenClient(self.env.kraken_api_key, self.env.kraken_api_secret)
        try:
            valid_pairs = await client.get_asset_pairs()
            balance = await client.get_balance()
            earn = KrakenEarn(client)

            errors = []
            for action in self.actions:
                if action.type == "order" and action.pair not in valid_pairs:
                    errors.append(f"'{action.name}': invalid pair '{action.pair}'")
                elif action.type == "earn" and action.asset:
                    strategy = await earn.find_strategy(action.asset, action.strategy)
                    if not strategy:
                        errors.append(
                            f"'{action.name}': no '{action.strategy}' strategy for '{action.asset}'"
                        )
                    elif action.asset not in balance:
                        balance_key = earn._find_balance_key(action.asset, balance)
                        if balance_key:
                            errors.append(
                                f"'{action.name}': use '{balance_key}' instead of '{action.asset}'"
                            )
                        else:
                            errors.append(
                                f"'{action.name}': asset '{action.asset}' not found in balance"
                            )
            if errors:
                raise ValueError(f"Invalid actions: {'; '.join(errors)}")
        finally:
            await client.close()
