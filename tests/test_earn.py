import pytest

from src.kraken.earn import KrakenEarn


@pytest.fixture
def earn(mock_kraken_client):
    return KrakenEarn(mock_kraken_client)


class TestFindStrategy:
    async def test_selects_restaked_with_longest_unbonding(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "items": [
                {"id": "short", "lock_type": {"type": "bonded", "unbonding_period": 7}},
                {"id": "long", "lock_type": {"type": "bonded", "unbonding_period": 28}},
                {"id": "flex", "lock_type": {"type": "flexible"}},
            ]
        }

        strategy = await earn.find_strategy("ETH", "restaked")

        assert strategy["id"] == "long"

    async def test_selects_bonded_with_shortest_unbonding(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "items": [
                {"id": "short", "lock_type": {"type": "bonded", "unbonding_period": 7}},
                {"id": "long", "lock_type": {"type": "bonded", "unbonding_period": 28}},
            ]
        }

        strategy = await earn.find_strategy("ETH", "bonded")

        assert strategy["id"] == "short"

    async def test_selects_flexible(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "items": [
                {"id": "bonded1", "lock_type": {"type": "bonded", "unbonding_period": 7}},
                {"id": "flex", "lock_type": {"type": "flexible"}},
            ]
        }

        strategy = await earn.find_strategy("ETH", "flexible")

        assert strategy["id"] == "flex"

    async def test_returns_none_when_no_match(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "items": [
                {"id": "bonded1", "lock_type": {"type": "bonded", "unbonding_period": 7}},
            ]
        }

        strategy = await earn.find_strategy("ETH", "flexible")

        assert strategy is None

    async def test_returns_none_when_no_strategies(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": []}

        strategy = await earn.find_strategy("ETH", "flexible")

        assert strategy is None


class TestStakeAfterPurchase:
    async def test_uses_balance_when_amount_is_none(self, earn, mock_kraken_client):
        # First call returns strategies, second call returns allocate result
        mock_kraken_client._request.side_effect = [
            {"items": [{"id": "strat1", "lock_type": {"type": "flexible"}}]},
            {"result": "success"},
        ]
        mock_kraken_client.get_balance.return_value = {"ETH": "1.5"}

        await earn.stake_asset("ETH", amount=None, strategy_type="flexible")

        # Check allocate was called with balance amount (data is positional arg)
        allocate_call = mock_kraken_client._request.call_args_list[-1]
        assert allocate_call[0][1] == "/0/private/Earn/Allocate"
        assert allocate_call[0][2]["amount"] == "1.5"

    async def test_uses_specified_amount(self, earn, mock_kraken_client):
        mock_kraken_client._request.side_effect = [
            {"items": [{"id": "strat1", "lock_type": {"type": "flexible"}}]},
            {"result": "success"},
        ]

        await earn.stake_asset("ETH", amount=0.5, strategy_type="flexible")

        allocate_call = mock_kraken_client._request.call_args_list[-1]
        assert allocate_call[0][2]["amount"] == "0.5"

    async def test_returns_none_when_no_strategy_found(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": []}

        result = await earn.stake_asset("ETH", strategy_type="flexible")

        assert result is None
