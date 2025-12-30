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
        amount: float,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        """
        Place a market order.

        Args:
            pair: Exact Kraken trading pair (e.g., "XXBTZUSD", "XETHZUSD")
            side: "buy" or "sell"
            amount: Amount in quote currency (USD) for buys, or base currency for sells
            validate_only: If True, only validate the order without executing

        Returns:
            Order result from Kraken API
        """

        # For market buys, we need to specify the volume in quote currency (USD)
        # using the "oflags=viqc" flag (volume in quote currency)
        data: dict[str, Any] = {
            "pair": pair,
            "type": side,
            "ordertype": "market",
        }

        if side == "buy":
            # For buys, amount is in USD - use volume in quote currency flag
            data["volume"] = str(amount)
            data["oflags"] = "viqc"
        else:
            # For sells, amount is in the base currency
            data["volume"] = str(amount)

        if validate_only:
            data["validate"] = True

        logger.info("Placing %s market order: %s USD on %s", side, amount, pair)

        result = await self.client._request("POST", "/0/private/AddOrder", data=data)

        if not validate_only:
            logger.info("Order placed successfully: %s", result.get("txid", []))

        return result

    async def get_open_orders(self) -> dict[str, Any]:
        """Get all open orders."""
        return await self.client._request("POST", "/0/private/OpenOrders")

    async def get_closed_orders(self) -> dict[str, Any]:
        """Get closed orders."""
        return await self.client._request("POST", "/0/private/ClosedOrders")

    async def cancel_order(self, txid: str) -> dict[str, Any]:
        """Cancel an open order."""
        return await self.client._request("POST", "/0/private/CancelOrder", data={"txid": txid})
