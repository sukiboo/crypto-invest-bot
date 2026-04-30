from unittest.mock import AsyncMock

import pytest

from src.bot import CryptoInvestBot
from src.schemas import ActionConfig


@pytest.fixture
def bot(mocker):
    mocker.patch("src.bot.KrakenClient")
    mocker.patch("src.bot.KrakenTrading")
    mocker.patch("src.bot.KrakenEarn")
    mocker.patch("src.bot.TelegramNotifier")
    mocker.patch("src.bot.JobScheduler")

    settings = mocker.Mock()
    settings.env = mocker.Mock()
    settings.actions = []
    settings.bot_name = "test-bot"

    instance = CryptoInvestBot(settings)
    instance.kraken_client.get_usd_balance = AsyncMock()
    instance.telegram.send_alert = AsyncMock()
    return instance


@pytest.fixture
def runway_action():
    return ActionConfig(
        name="Check runway",
        type="check_runway",
        schedule="0 0 * * *",
        days=7,
    )


def _buy(name, amount, schedule="0 12 * * *", pair="ETHUSD"):
    return ActionConfig(
        name=name, type="order", schedule=schedule, pair=pair, side="buy", amount=amount
    )


class TestCheckRunway:
    async def test_ok_when_balance_covers_required(self, bot, runway_action):
        bot.settings.actions = [_buy("Buy ETH", 10.0)]
        bot.kraken_client.get_usd_balance.return_value = 10_000.0

        result = await bot._execute_check_runway(runway_action)

        assert result["ok"] is True
        assert bot.telegram.send_alert.call_args.kwargs["quiet"] is True
        assert "runway ok" in bot.telegram.send_alert.call_args.args[0]

    async def test_low_when_balance_below_required(self, bot, runway_action):
        bot.settings.actions = [_buy("Buy ETH", 10.0)]
        bot.kraken_client.get_usd_balance.return_value = 5.0

        result = await bot._execute_check_runway(runway_action)

        assert result["ok"] is False
        assert bot.telegram.send_alert.call_args.kwargs["quiet"] is False
        msg = bot.telegram.send_alert.call_args.args[0]
        assert "runway low" in msg
        assert "Buy ETH" in msg

    async def test_only_buy_orders_count_toward_required(self, bot, runway_action):
        bot.settings.actions = [
            _buy("Buy ETH", 10.0),
            ActionConfig(
                name="Sell BTC",
                type="order",
                schedule="0 12 * * *",
                pair="XBTUSD",
                side="sell",
                amount=0.001,
            ),
            ActionConfig(
                name="Stake ETH",
                type="earn",
                schedule="0 12 * * *",
                asset="ETH",
                strategy="flexible",
            ),
        ]
        bot.kraken_client.get_usd_balance.return_value = 10_000.0

        result = await bot._execute_check_runway(runway_action)

        # Daily $10 buy over 7 days ≈ $70; allow ±1 fire for clock boundary
        assert 60.0 <= result["required"] <= 80.0
        msg = bot.telegram.send_alert.call_args.args[0]
        assert "Sell BTC" not in msg
        assert "Stake ETH" not in msg

    async def test_no_buys_means_zero_required(self, bot, runway_action):
        bot.settings.actions = [
            ActionConfig(
                name="Stake ETH",
                type="earn",
                schedule="0 12 * * *",
                asset="ETH",
                strategy="flexible",
            ),
        ]
        bot.kraken_client.get_usd_balance.return_value = 0.0

        result = await bot._execute_check_runway(runway_action)

        assert result["required"] == 0.0
        assert result["ok"] is True
        assert bot.telegram.send_alert.call_args.kwargs["quiet"] is True

    async def test_low_message_includes_breakdown_per_buy(self, bot, runway_action):
        bot.settings.actions = [
            _buy("Buy ETH", 25.0, pair="ETHUSD"),
            _buy("Buy SOL", 15.0, pair="SOLUSD"),
        ]
        bot.kraken_client.get_usd_balance.return_value = 0.0

        await bot._execute_check_runway(runway_action)

        msg = bot.telegram.send_alert.call_args.args[0]
        assert "Buy ETH" in msg
        assert "Buy SOL" in msg
        assert "$25.00" in msg
        assert "$15.00" in msg

    async def test_required_scales_with_amount_and_frequency(self, bot, runway_action):
        # Twice-daily $50 buy over 7d ≈ $700 (allow ±1 fire)
        bot.settings.actions = [_buy("Buy ETH", 50.0, schedule="0 0,12 * * *")]
        bot.kraken_client.get_usd_balance.return_value = 10_000.0

        result = await bot._execute_check_runway(runway_action)

        assert 650.0 <= result["required"] <= 750.0
