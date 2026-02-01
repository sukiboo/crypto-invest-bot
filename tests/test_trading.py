from unittest.mock import AsyncMock

import pytest

from src.kraken.trading import KrakenTrading


@pytest.fixture
def trading(mock_kraken_client):
    return KrakenTrading(mock_kraken_client)


class TestPlaceMarketOrder:
    async def test_buy_order_sets_viqc_flag(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {"txid": ["ABC123"]}

        await trading.place_market_order(pair="XETHZUSD", side="buy", amount=100.0)

        call_args = mock_kraken_client._request.call_args
        data = call_args.kwargs["data"]
        assert data["oflags"] == "viqc"
        assert data["volume"] == "100.0"

    async def test_sell_order_no_viqc_flag(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {"txid": ["ABC123"]}

        await trading.place_market_order(pair="XETHZUSD", side="sell", amount=0.5)

        call_args = mock_kraken_client._request.call_args
        data = call_args.kwargs["data"]
        assert "oflags" not in data
        assert data["volume"] == "0.5"


class TestGetFilledOrderDetails:
    async def test_returns_values_when_order_closed(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "ABC123": {
                "status": "closed",
                "vol_exec": "0.05",
                "price": "2500.00",
            }
        }

        vol_exec, price = await trading.get_filled_order_details("ABC123")

        assert vol_exec == "0.05"
        assert price == 2500.00

    async def test_returns_none_for_zero_vol_exec(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "ABC123": {
                "status": "closed",
                "vol_exec": "0",
                "price": "2500.00",
            }
        }

        vol_exec, price = await trading.get_filled_order_details("ABC123")

        assert vol_exec is None
        assert price == 2500.00

    async def test_returns_none_for_empty_vol_exec(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "ABC123": {
                "status": "closed",
                "vol_exec": "",
                "price": "2500.00",
            }
        }

        vol_exec, price = await trading.get_filled_order_details("ABC123")

        assert vol_exec is None

    async def test_returns_none_for_zero_price(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "ABC123": {
                "status": "closed",
                "vol_exec": "0.05",
                "price": "0",
            }
        }

        vol_exec, price = await trading.get_filled_order_details("ABC123")

        assert vol_exec == "0.05"
        assert price is None

    async def test_retries_until_closed(self, trading, mock_kraken_client, mocker):
        mocker.patch("src.kraken.trading.asyncio.sleep", new_callable=AsyncMock)

        # First two calls return pending, third returns closed
        mock_kraken_client._request.side_effect = [
            {"ABC123": {"status": "pending", "vol_exec": "", "price": ""}},
            {"ABC123": {"status": "open", "vol_exec": "", "price": ""}},
            {"ABC123": {"status": "closed", "vol_exec": "0.05", "price": "2500.00"}},
        ]

        vol_exec, price = await trading.get_filled_order_details("ABC123", max_attempts=5)

        assert mock_kraken_client._request.call_count == 3
        assert vol_exec == "0.05"
        assert price == 2500.00
