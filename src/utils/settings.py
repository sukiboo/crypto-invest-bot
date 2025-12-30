from pathlib import Path

import yaml

from src.schemas import ActionConfig, AppConfig, EnvSettings


class Settings:
    def __init__(self, config_path: str | Path = "settings.yaml") -> None:
        self.env = EnvSettings()  # pyright: ignore[reportCallIssue]
        self.app = self._load_yaml_config(config_path)

    def _load_yaml_config(self, config_path: str | Path) -> AppConfig:
        """Load and validate the YAML configuration file."""
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
