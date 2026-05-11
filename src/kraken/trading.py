import asyncio
import logging
from typing import Any, Literal

from src.kraken.client import KrakenClient

logger = logging.getLogger(__name__)


class KrakenTrading:
    def __init__(self, client: KrakenClient) -> None:
        self.client = client

    async def place_market_order(
        self,
        pair: str,
        side: Literal["buy", "sell"],
        amount: float | None,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        """
        Place a market order.

        Args:
            pair: Exact Kraken trading pair (e.g., "XXBTZUSD", "XETHZUSD")
            side: "buy" or "sell"
            amount: For buys, amount in quote currency (e.g. USD); None = use full
                quote balance. For sells, amount in base currency.
            validate_only: If True, only validate the order without executing

        Returns:
            Order result from Kraken API, or {} if skipped (zero balance for amount=None buy).
        """

        if amount is None:
            if side != "buy":
                raise ValueError("amount=None is only supported for buy orders")
            quote = await self.client.get_pair_quote(pair)
            amount = await self.client.get_asset_balance(quote)
            if amount <= 0:
                logger.info("Skipping %s buy: %s balance is 0", pair, quote)
                return {}
            logger.info("Buying %s with full %s balance: %s", pair, quote, amount)

        data: dict[str, Any] = {
            "pair": pair,
            "type": side,
            "ordertype": "market",
            "volume": str(amount),
        }

        if side == "buy":
            # viqc = volume in quote currency; fcib = fee in base currency
            # so the full quote balance can be spent without reserving fee.
            data["oflags"] = "viqc,fcib"

        if validate_only:
            data["validate"] = True

        logger.info("Placing %s market order: %s on %s", side, amount, pair)

        result = await self.client._request("POST", "/0/private/AddOrder", data=data)

        if not validate_only:
            logger.info("Order placed successfully: %s", result.get("txid", []))

        return result

    async def get_open_orders(self) -> dict[str, Any]:
        return await self.client._request("POST", "/0/private/OpenOrders")

    async def get_closed_orders(self) -> dict[str, Any]:
        return await self.client._request("POST", "/0/private/ClosedOrders")

    async def cancel_order(self, txid: str) -> dict[str, Any]:
        return await self.client._request("POST", "/0/private/CancelOrder", data={"txid": txid})

    async def query_orders(self, txid: str | list[str]) -> dict[str, Any]:
        """
        Query order details by transaction ID(s).

        Args:
            txid: Single transaction ID or list of transaction IDs

        Returns:
            Order details from Kraken API
        """
        return await self.client._request(
            "POST",
            "/0/private/QueryOrders",
            data={"txid": ",".join(txid) if isinstance(txid, list) else txid},
        )

    async def get_filled_order_details(
        self, txid: str | list[str], max_attempts: int = 5, delay: float = 1.0
    ) -> tuple[str | None, float | None, float | None, float | None]:
        if isinstance(txid, list):
            if not txid:
                return None, None, None, None
            else:
                txid = txid[0]

        order_info: dict[str, Any] = {}

        for attempt in range(max_attempts):
            try:
                order_details = await self.query_orders(txid)
                order_info = order_details.get(txid, {})
                if order_info.get("status") == "closed":
                    break
                logger.debug(
                    "Order %s status: %s (%d/%d)",
                    txid,
                    order_info.get("status"),
                    attempt + 1,
                    max_attempts,
                )
            except Exception as e:
                logger.warning("Failed to query order %s: %s", txid, e)
            await asyncio.sleep(delay)

        vol_exec = order_info.get("vol_exec")
        price = order_info.get("price")
        cost = order_info.get("cost")
        fee = order_info.get("fee")

        vol_exec_result = None if not vol_exec or vol_exec in ("0", "0.00000000") else vol_exec
        price_result = None if not price or float(price) == 0 else float(price)
        cost_result = None if not cost or float(cost) == 0 else float(cost)
        fee_result = None if fee is None else float(fee)

        if vol_exec_result is None:
            logger.warning("Order %s: vol_exec not available", txid)
        if price_result is None:
            logger.warning("Order %s: price not available", txid)
        if cost_result is None:
            logger.warning("Order %s: cost not available", txid)

        return vol_exec_result, price_result, cost_result, fee_result
