import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, NamedTuple

from src.kraken.client import KrakenClient
from src.schemas import OrderSide

logger = logging.getLogger(__name__)


class FilledOrder(NamedTuple):
    gross_base: float
    fee_base: float
    gross_quote: float
    fee_quote: float


async def _poll[T](
    fn: Callable[[], Awaitable[T | None]], max_attempts: int, delay: float
) -> T | None:
    """Call fn repeatedly until it returns a non-None value or attempts run out."""
    for _ in range(max_attempts):
        if (result := await fn()) is not None:
            return result
        await asyncio.sleep(delay)
    return None


class KrakenTrading:
    def __init__(self, client: KrakenClient) -> None:
        self.client = client

    async def place_market_order(
        self,
        pair: str,
        side: OrderSide,
        amount: float | None,
    ) -> dict[str, Any] | None:
        # amount is quote-denominated for buys, base-denominated for sells.
        # amount=None means "use the full balance of the relevant side".
        # Returns None to signal "skipped: nothing to spend/sell" (distinct from any
        # other empty/malformed API response, which still surfaces as an error).
        if amount is None:
            base, quote = await self.client.get_pair_symbols(pair)
            asset = quote if side == "buy" else base
            amount = await self.client.get_asset_balance(asset)
            if amount <= 0:
                logger.info("Skipping %s %s: %s balance is 0", pair, side, asset)
                return None
            logger.info("Full-balance %s on %s: %s %s", side, pair, amount, asset)

        data: dict[str, Any] = {
            "pair": pair,
            "type": side,
            "ordertype": "market",
            "volume": str(amount),
        }
        if side == "buy":
            # viqc = volume in quote currency; fcib = fee in base currency,
            # so the full quote balance can be spent without reserving for fees.
            data["oflags"] = "viqc,fcib"

        logger.info("Placing %s market order: %s on %s", side, amount, pair)
        result = await self.client._request("/0/private/AddOrder", data=data)
        logger.info("Order placed: %s", result.get("txid", []))
        return result

    async def get_open_orders(self) -> dict[str, Any]:
        return await self.client._request("/0/private/OpenOrders")

    async def get_closed_orders(self) -> dict[str, Any]:
        return await self.client._request("/0/private/ClosedOrders")

    async def cancel_order(self, txid: str) -> dict[str, Any]:
        return await self.client._request("/0/private/CancelOrder", data={"txid": txid})

    async def query_orders(self, txid: str | list[str]) -> dict[str, Any]:
        return await self.client._request(
            "/0/private/QueryOrders",
            data={"txid": ",".join(txid) if isinstance(txid, list) else txid},
        )

    async def get_filled_order(
        self,
        txid: str | list[str],
        side: OrderSide,
        max_attempts: int = 10,
        delay: float = 1.0,
    ) -> FilledOrder | None:
        """Resolve a placed order to the precise values posted to the ledger.

        `/AddOrder` returns an order ID (`O...`), but ledger trade entries reference
        trades by trade ID (`T...`). Polls `/0/private/TradesHistory` to map the
        order ID to its trade IDs, then `/0/private/Ledgers` for the entries whose
        `refid` matches. Returns gross/fee on both sides of the trade as recorded by
        Kraken — no approximations. Returns None if no matching entries surface
        within the retry budget."""
        if isinstance(txid, list):
            if not txid:
                return None
            txid = txid[0]

        async def _fetch_filled_order() -> FilledOrder | None:
            trades_result = await self.client._request("/0/private/TradesHistory")
            trade_ids = {
                tid
                for tid, t in trades_result.get("trades", {}).items()
                if t.get("ordertxid") == txid
            }
            if not trade_ids:
                return None
            entries = await self.client.get_ledger_entries(ledger_type="trade")
            matches = [e for e in entries.values() if e.get("refid") in trade_ids]
            received = [e for e in matches if float(e.get("amount", 0)) > 0]
            paid = [e for e in matches if float(e.get("amount", 0)) < 0]
            if not (received and paid):
                return None
            # For buys: received side is base (fee in base); paid side is quote.
            # For sells: received side is quote (fee in quote); paid side is base.
            base_side, quote_side = (received, paid) if side == "buy" else (paid, received)
            return FilledOrder(
                gross_base=abs(sum(float(e["amount"]) for e in base_side)),
                fee_base=sum(float(e["fee"]) for e in base_side),
                gross_quote=abs(sum(float(e["amount"]) for e in quote_side)),
                fee_quote=sum(float(e["fee"]) for e in quote_side),
            )

        result = await _poll(_fetch_filled_order, max_attempts, delay)
        if result is None:
            logger.warning("No ledger entries found for order %s", txid)
        else:
            logger.info(
                "Order %s filled: gross_base=%s fee_base=%s gross_quote=%s fee_quote=%s",
                txid,
                result.gross_base,
                result.fee_base,
                result.gross_quote,
                result.fee_quote,
            )
        return result
