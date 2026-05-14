from unittest.mock import AsyncMock

import pytest

from src.kraken.trading import KrakenTrading


@pytest.fixture
def trading(mock_kraken_client):
    return KrakenTrading(mock_kraken_client)


class TestPlaceMarketOrder:
    async def test_buy_order_sets_viqc_fcib_flags(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {"txid": ["ABC123"]}

        await trading.place_market_order(pair="ETHUSD", side="buy", amount=100.0)

        data = mock_kraken_client._request.call_args.kwargs["data"]
        assert data["oflags"] == "viqc,fcib"
        assert data["volume"] == "100.0"

    async def test_sell_order_no_oflags(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {"txid": ["ABC123"]}

        await trading.place_market_order(pair="ETHUSD", side="sell", amount=0.5)

        data = mock_kraken_client._request.call_args.kwargs["data"]
        assert "oflags" not in data
        assert data["volume"] == "0.5"

    async def test_buy_with_amount_none_spends_full_quote_balance(
        self, trading, mock_kraken_client
    ):
        mock_kraken_client.get_pair_symbols = AsyncMock(return_value=("ETH", "USD"))
        mock_kraken_client.get_asset_balance = AsyncMock(return_value=100.0)
        mock_kraken_client._request.return_value = {"txid": ["ABC123"]}

        await trading.place_market_order(pair="ETHUSD", side="buy", amount=None)

        mock_kraken_client.get_asset_balance.assert_awaited_once_with("USD")
        data = mock_kraken_client._request.call_args.kwargs["data"]
        assert data["volume"] == "100.0"
        assert data["oflags"] == "viqc,fcib"

    async def test_sell_with_amount_none_dumps_full_base_balance(self, trading, mock_kraken_client):
        mock_kraken_client.get_pair_symbols = AsyncMock(return_value=("ETH", "USD"))
        mock_kraken_client.get_asset_balance = AsyncMock(return_value=2.5)
        mock_kraken_client._request.return_value = {"txid": ["XYZ"]}

        await trading.place_market_order(pair="ETHUSD", side="sell", amount=None)

        mock_kraken_client.get_asset_balance.assert_awaited_once_with("ETH")
        data = mock_kraken_client._request.call_args.kwargs["data"]
        assert data["volume"] == "2.5"
        assert "oflags" not in data

    async def test_skipped_when_balance_is_zero(self, trading, mock_kraken_client):
        mock_kraken_client.get_pair_symbols = AsyncMock(return_value=("ETH", "USD"))
        mock_kraken_client.get_asset_balance = AsyncMock(return_value=0.0)

        result = await trading.place_market_order(pair="ETHUSD", side="buy", amount=None)

        assert result == {}
        mock_kraken_client._request.assert_not_called()


class TestGetFilledOrder:
    async def test_buy_reads_base_and_quote_from_ledger(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {"trades": {"T1": {"ordertxid": "ABC123"}}}
        mock_kraken_client.get_ledger_entries = AsyncMock(
            return_value={
                "L1": {"refid": "T1", "amount": "0.05", "fee": "0.0002"},
                "L2": {"refid": "T1", "amount": "-125.00", "fee": "0"},
            }
        )

        filled = await trading.get_filled_order("ABC123", side="buy")

        assert filled is not None
        assert filled.gross_base == 0.05
        assert filled.fee_base == 0.0002
        assert filled.gross_quote == 125.00
        assert filled.fee_quote == 0.0

    async def test_sell_swaps_received_and_paid_sides(self, trading, mock_kraken_client):
        # On a sell, the positive ledger entry is the quote credit (with quote fee)
        # and the negative entry is the base debit (no fee since fcib is buy-only).
        mock_kraken_client._request.return_value = {"trades": {"T1": {"ordertxid": "ABC123"}}}
        mock_kraken_client.get_ledger_entries = AsyncMock(
            return_value={
                "L1": {"refid": "T1", "amount": "-0.05", "fee": "0"},
                "L2": {"refid": "T1", "amount": "125.00", "fee": "0.32"},
            }
        )

        filled = await trading.get_filled_order("ABC123", side="sell")

        assert filled is not None
        assert filled.gross_base == 0.05
        assert filled.fee_base == 0.0
        assert filled.gross_quote == 125.00
        assert filled.fee_quote == 0.32

    async def test_sums_across_split_fills(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "trades": {"T1": {"ordertxid": "ABC123"}, "T2": {"ordertxid": "ABC123"}}
        }
        mock_kraken_client.get_ledger_entries = AsyncMock(
            return_value={
                "L1": {"refid": "T1", "amount": "0.03", "fee": "0.0001"},
                "L2": {"refid": "T2", "amount": "0.02", "fee": "0.0001"},
                "L3": {"refid": "T1", "amount": "-75.00", "fee": "0"},
                "L4": {"refid": "T2", "amount": "-50.00", "fee": "0"},
            }
        )

        filled = await trading.get_filled_order("ABC123", side="buy")

        assert filled is not None
        assert filled.gross_base == pytest.approx(0.05)
        assert filled.fee_base == pytest.approx(0.0002)
        assert filled.gross_quote == 125.00

    async def test_ignores_entries_from_unrelated_trades(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {"trades": {"T1": {"ordertxid": "ABC123"}}}
        mock_kraken_client.get_ledger_entries = AsyncMock(
            return_value={
                "L1": {"refid": "TOTHER", "amount": "1.0", "fee": "0.01"},
                "L2": {"refid": "T1", "amount": "0.05", "fee": "0.0002"},
                "L3": {"refid": "T1", "amount": "-125.00", "fee": "0"},
            }
        )

        filled = await trading.get_filled_order("ABC123", side="buy")

        assert filled.gross_base == 0.05

    async def test_ignores_trades_from_other_orders(self, trading, mock_kraken_client):
        mock_kraken_client._request.return_value = {
            "trades": {
                "T1": {"ordertxid": "ABC123"},
                "T2": {"ordertxid": "OTHER_ORDER"},
            }
        }
        mock_kraken_client.get_ledger_entries = AsyncMock(
            return_value={
                "L1": {"refid": "T1", "amount": "0.05", "fee": "0.0002"},
                "L2": {"refid": "T1", "amount": "-125.00", "fee": "0"},
                "L3": {"refid": "T2", "amount": "1.0", "fee": "0.01"},
                "L4": {"refid": "T2", "amount": "-2000.00", "fee": "0"},
            }
        )

        filled = await trading.get_filled_order("ABC123", side="buy")

        assert filled.gross_base == 0.05
        assert filled.gross_quote == 125.00

    async def test_returns_none_for_empty_txid_list(self, trading):
        assert await trading.get_filled_order([], side="buy") is None

    async def test_returns_none_when_trades_history_empty(
        self, trading, mock_kraken_client, mocker
    ):
        mocker.patch("src.kraken.trading.asyncio.sleep", new_callable=AsyncMock)
        mock_kraken_client._request.return_value = {"trades": {}}

        filled = await trading.get_filled_order("ABC123", side="buy", max_attempts=2)

        assert filled is None

    async def test_returns_none_when_ledger_empty(self, trading, mock_kraken_client, mocker):
        mocker.patch("src.kraken.trading.asyncio.sleep", new_callable=AsyncMock)
        mock_kraken_client._request.return_value = {"trades": {"T1": {"ordertxid": "ABC123"}}}
        mock_kraken_client.get_ledger_entries = AsyncMock(return_value={})

        filled = await trading.get_filled_order("ABC123", side="buy", max_attempts=2)

        assert filled is None

    async def test_polls_until_entries_appear(self, trading, mock_kraken_client, mocker):
        mocker.patch("src.kraken.trading.asyncio.sleep", new_callable=AsyncMock)
        mock_kraken_client._request.return_value = {"trades": {"T1": {"ordertxid": "ABC123"}}}
        mock_kraken_client.get_ledger_entries = AsyncMock(
            side_effect=[
                {},
                {},
                {
                    "L1": {"refid": "T1", "amount": "0.05", "fee": "0.0002"},
                    "L2": {"refid": "T1", "amount": "-125.00", "fee": "0"},
                },
            ]
        )

        filled = await trading.get_filled_order("ABC123", side="buy", max_attempts=5)

        assert mock_kraken_client.get_ledger_entries.call_count == 3
        assert filled is not None
        assert filled.gross_base == 0.05
