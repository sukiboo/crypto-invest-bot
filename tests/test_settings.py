import pytest
from pydantic import ValidationError

from src.utils.settings import Settings


@pytest.fixture
def valid_yaml_config(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
bot_name: test-bot
actions:
  - name: Buy ETH
    type: order
    schedule: "0 12 * * *"
    pair: ETHUSD
    amount: 100.0
"""
    )
    return config_file


@pytest.fixture
def invalid_yaml_config(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
bot_name: test-bot
actions:
  - name: Bad Action
    type: order
    schedule: "0 12 * * *"
    # missing pair and amount
"""
    )
    return config_file


class TestSettings:
    def test_loads_valid_yaml(self, valid_yaml_config, mocker):
        # Mock EnvSettings to avoid needing .env file
        mocker.patch("src.utils.settings.EnvSettings")

        settings = Settings(config_path=valid_yaml_config)

        assert settings.bot_name == "test-bot"
        assert len(settings.actions) == 1
        assert settings.actions[0].name == "Buy ETH"

    def test_raises_on_missing_file(self, mocker):
        mocker.patch("src.utils.settings.EnvSettings")

        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            Settings(config_path="/nonexistent/path/settings.yaml")

    def test_validates_actions_through_pydantic(self, invalid_yaml_config, mocker):
        mocker.patch("src.utils.settings.EnvSettings")

        with pytest.raises(ValidationError):
            Settings(config_path=invalid_yaml_config)
