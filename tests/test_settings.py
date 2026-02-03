from unittest.mock import AsyncMock

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


class TestSettingsValidate:
    @pytest.fixture
    def mock_kraken(self, mocker):
        mock_client = mocker.patch("src.utils.settings.KrakenClient")
        mock_earn = mocker.patch("src.utils.settings.KrakenEarn")

        client_instance = mock_client.return_value
        client_instance.get_asset_pairs = AsyncMock(return_value={"ETHUSD", "XBTUSD", "SOLUSD"})
        client_instance.get_balance = AsyncMock(
            return_value={"XETH": "1.0", "XXBT": "0.1", "SOL": "1.0"}
        )
        client_instance.close = AsyncMock()

        async def mock_find_strategy(asset, strategy_type=None):
            valid = {"ETH", "XETH", "XBT", "XXBT", "SOL"}
            return {"id": "test"} if asset in valid else None

        earn_instance = mock_earn.return_value
        earn_instance.find_strategy = AsyncMock(side_effect=mock_find_strategy)
        earn_instance._find_balance_key = lambda a, b: f"X{a}" if f"X{a}" in b else None
        return client_instance

    @pytest.fixture
    def config_with_invalid_pair(self, tmp_path):
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(
            """
bot_name: test-bot
actions:
  - name: Buy FOO
    type: order
    schedule: "0 12 * * *"
    pair: FOOUSD
    amount: 100.0
"""
        )
        return config_file

    @pytest.fixture
    def config_with_wrong_earn_asset(self, tmp_path):
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(
            """
bot_name: test-bot
actions:
  - name: Stake ETH
    type: earn
    schedule: "0 12 * * *"
    asset: ETH
    strategy: flexible
"""
        )
        return config_file

    @pytest.mark.asyncio
    async def test_valid_config_passes(self, valid_yaml_config, mock_kraken, mocker):
        mocker.patch("src.utils.settings.EnvSettings")
        settings = Settings(config_path=valid_yaml_config)

        await settings.validate()

    @pytest.mark.asyncio
    async def test_invalid_pair_fails(self, config_with_invalid_pair, mock_kraken, mocker):
        mocker.patch("src.utils.settings.EnvSettings")
        settings = Settings(config_path=config_with_invalid_pair)

        with pytest.raises(ValueError, match="invalid pair 'FOOUSD'"):
            await settings.validate()

    @pytest.mark.asyncio
    async def test_wrong_earn_asset_suggests_correct(
        self, config_with_wrong_earn_asset, mock_kraken, mocker
    ):
        mocker.patch("src.utils.settings.EnvSettings")
        settings = Settings(config_path=config_with_wrong_earn_asset)

        with pytest.raises(ValueError, match="use 'XETH' instead of 'ETH'"):
            await settings.validate()
