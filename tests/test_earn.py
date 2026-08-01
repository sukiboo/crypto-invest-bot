from unittest.mock import AsyncMock

import pytest

from src.kraken.earn import KrakenEarn

BONDED = {
    "id": "bonded1",
    "lock_type": {"type": "bonded", "unbonding_period": 604800},
    "can_allocate": True,
}
# Allocatable, but "instant" is not a keyword -- reachable only by explicit id.
INSTANT = {"id": "instant1", "lock_type": {"type": "instant"}, "can_allocate": True}
# Kraken auto-allocates idle spot into flex, so it is never allocatable via the API.
FLEX = {"id": "flex1", "lock_type": {"type": "flex"}, "can_allocate": False}


@pytest.fixture
def earn(mock_kraken_client):
    return KrakenEarn(mock_kraken_client)


class TestFindStrategy:
    async def test_selects_bonded(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": [BONDED, INSTANT, FLEX]}

        strategy = await earn.find_strategy("ETH", "bonded")

        assert strategy["id"] == "bonded1"

    async def test_selects_explicit_id_of_any_lock_type(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": [BONDED, INSTANT]}

        strategy = await earn.find_strategy("ETH", "instant1")

        assert strategy["id"] == "instant1"

    async def test_skips_non_allocatable_of_matching_lock_type(self, earn, mock_kraken_client):
        # ETH restaking stayed visible in the API after Kraken closed it to new allocations.
        closed = {
            "id": "closed",
            "lock_type": {"type": "bonded", "unbonding_period": 1209600},
            "can_allocate": False,
        }
        mock_kraken_client._request.return_value = {"items": [BONDED, closed]}

        strategy = await earn.find_strategy("ETH", "bonded")

        assert strategy["id"] == "bonded1"

    async def test_raises_when_lock_type_ambiguous(self, earn, mock_kraken_client):
        other = {
            "id": "bonded2",
            "lock_type": {"type": "bonded", "unbonding_period": 1209600},
            "can_allocate": True,
        }
        mock_kraken_client._request.return_value = {"items": [BONDED, other]}

        with pytest.raises(ValueError, match="set one explicitly"):
            await earn.find_strategy("ETH", "bonded")

    async def test_raises_when_lock_type_unavailable(self, earn, mock_kraken_client):
        # ADA, MINA and TAO offer instant but no bonded strategy.
        mock_kraken_client._request.return_value = {"items": [INSTANT, FLEX]}

        with pytest.raises(ValueError, match="no allocatable 'bonded' strategy"):
            await earn.find_strategy("ADA", "bonded")

    async def test_raises_when_only_flex_available(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": [FLEX]}

        with pytest.raises(ValueError, match="no allocatable strategy"):
            await earn.find_strategy("USDC", "bonded")

    async def test_raises_on_unknown_id(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": [BONDED]}

        with pytest.raises(ValueError, match="unknown strategy 'ESNOPE-XXXXX-YYYYYY'"):
            await earn.find_strategy("ETH", "ESNOPE-XXXXX-YYYYYY")

    async def test_raises_on_id_closed_to_allocations(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": [BONDED, FLEX]}

        with pytest.raises(ValueError, match="closed to new allocations"):
            await earn.find_strategy("ETH", "flex1")

    async def test_raises_when_no_strategies(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": []}

        with pytest.raises(ValueError, match="no earn strategies exist"):
            await earn.find_strategy("ETH", "bonded")


class TestStakeAsset:
    async def test_uses_balance_when_amount_is_none(self, earn, mock_kraken_client):
        # find_strategy → _request, then allocate → _request
        mock_kraken_client._request.side_effect = [
            {"items": [BONDED]},
            {"result": "success"},
        ]
        mock_kraken_client.get_asset_balance = AsyncMock(return_value=1.5)

        result = await earn.stake_asset("ETH", "bonded", amount=None)

        allocate_call = mock_kraken_client._request.call_args_list[-1]
        assert allocate_call.args[0] == "/0/private/Earn/Allocate"
        assert allocate_call.kwargs["data"]["amount"] == "1.5"
        assert result["amount"] == 1.5

    async def test_uses_specified_amount(self, earn, mock_kraken_client):
        mock_kraken_client._request.side_effect = [
            {"items": [BONDED]},
            {"result": "success"},
        ]

        result = await earn.stake_asset("ETH", "bonded", amount=0.5)

        allocate_call = mock_kraken_client._request.call_args_list[-1]
        assert allocate_call.kwargs["data"]["amount"] == "0.5"
        assert result["amount"] == 0.5

    async def test_raises_when_no_strategy_found(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": []}

        with pytest.raises(ValueError, match="no earn strategies exist"):
            await earn.stake_asset("ETH", "bonded")

    async def test_returns_none_when_balance_is_zero(self, earn, mock_kraken_client):
        mock_kraken_client._request.return_value = {"items": [BONDED]}
        mock_kraken_client.get_asset_balance = AsyncMock(return_value=0.0)

        result = await earn.stake_asset("ETH", "bonded", amount=None)

        assert result is None
