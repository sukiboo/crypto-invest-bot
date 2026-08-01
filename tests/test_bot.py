import re
from unittest.mock import AsyncMock

import pytest

from src.actions.check_runway import CheckRunwayAction
from src.schemas import ActionConfig


async def _resolve_pair_symbols(pair: str) -> tuple[str, str]:
    return {
        "ETHUSD": ("ETH", "USD"),
        "SOLUSD": ("SOL", "USD"),
        "XBTUSD": ("XBT", "USD"),
    }[pair]


@pytest.fixture
def ctx(mocker):
    ctx = mocker.Mock()
    ctx.kraken_client = mocker.Mock()
    ctx.kraken_client.get_pair_symbols = AsyncMock(side_effect=_resolve_pair_symbols)
    ctx.kraken_client.get_balance = AsyncMock(return_value={})
    ctx.kraken_client.get_asset_balance = AsyncMock(return_value=10_000.0)
    ctx.earn = mocker.Mock()
    ctx.earn.get_allocations_by_asset = AsyncMock(return_value={})
    ctx.telegram = mocker.Mock()
    ctx.telegram.send_alert = AsyncMock()
    ctx.settings = mocker.Mock()
    ctx.settings.actions = []
    return ctx


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


class TestCheckRunwayAction:
    async def test_quiet_alert_when_balance_covers_required(self, ctx, runway_action):
        ctx.settings.actions = [_buy("Buy ETH", 10.0)]
        ctx.kraken_client.get_asset_balance.return_value = 10_000.0

        await CheckRunwayAction().execute(runway_action, ctx)

        assert ctx.telegram.send_alert.call_args.kwargs["quiet"] is True
        assert "runway ok" in ctx.telegram.send_alert.call_args.args[0]

    async def test_loud_alert_when_balance_below_required(self, ctx, runway_action):
        ctx.settings.actions = [_buy("Buy ETH", 10.0)]
        ctx.kraken_client.get_asset_balance.return_value = 5.0

        await CheckRunwayAction().execute(runway_action, ctx)

        assert ctx.telegram.send_alert.call_args.kwargs["quiet"] is False
        msg = ctx.telegram.send_alert.call_args.args[0]
        assert "runway low" in msg
        assert "Buy ETH" in msg

    async def test_non_buy_actions_excluded_from_required(self, ctx, runway_action):
        ctx.settings.actions = [
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
                strategy="bonded",
            ),
        ]
        ctx.kraken_client.get_asset_balance.return_value = 10_000.0

        await CheckRunwayAction().execute(runway_action, ctx)

        msg = ctx.telegram.send_alert.call_args.args[0]
        assert "Sell BTC" not in msg
        assert "Stake ETH" not in msg

    async def test_no_buys_emits_quiet_empty_message(self, ctx, runway_action):
        ctx.settings.actions = [
            ActionConfig(
                name="Stake ETH",
                type="earn",
                schedule="0 12 * * *",
                asset="ETH",
                strategy="bonded",
            ),
        ]

        await CheckRunwayAction().execute(runway_action, ctx)

        assert ctx.telegram.send_alert.call_args.kwargs["quiet"] is True
        assert "no buy actions scheduled" in ctx.telegram.send_alert.call_args.args[0]

    async def test_message_includes_breakdown_per_buy(self, ctx, runway_action):
        ctx.settings.actions = [
            _buy("Buy ETH", 25.0, pair="ETHUSD"),
            _buy("Buy SOL", 15.0, pair="SOLUSD"),
        ]
        ctx.kraken_client.get_asset_balance.return_value = 0.0

        await CheckRunwayAction().execute(runway_action, ctx)

        msg = ctx.telegram.send_alert.call_args.args[0]
        assert "Buy ETH" in msg
        assert "Buy SOL" in msg
        assert "25.00 USD" in msg
        assert "15.00 USD" in msg

    async def test_required_scales_with_amount_and_frequency(self, ctx, runway_action):
        # Twice-daily $50 buy over 7d ≈ 14 fires (allow ±1 for clock boundary)
        ctx.settings.actions = [_buy("Buy ETH", 50.0, schedule="0 0,12 * * *")]
        ctx.kraken_client.get_asset_balance.return_value = 10_000.0

        await CheckRunwayAction().execute(runway_action, ctx)

        msg = ctx.telegram.send_alert.call_args.args[0]
        match = re.search(r"Buy ETH: (\d+) x 50\.00", msg)
        assert match is not None
        assert 13 <= int(match.group(1)) <= 14

    async def test_earn_balance_counts_toward_available(self, ctx, runway_action):
        ctx.settings.actions = [_buy("Buy ETH", 100.0)]
        # Spot only $50 (less than 7*100 required), but earn allocations cover the rest
        ctx.kraken_client.get_asset_balance.return_value = 50.0
        ctx.earn.get_allocations_by_asset.return_value = {"ZUSD": 5_000.0}

        await CheckRunwayAction().execute(runway_action, ctx)

        assert ctx.telegram.send_alert.call_args.kwargs["quiet"] is True
