from typing import Any

from src.actions.base import Action, ActionContext
from src.kraken.trading import KrakenTrading
from src.schemas import ActionConfig


class OrderAction(Action):
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> str:
        if config.order_type != "market":
            raise ValueError(f"Unsupported order type: {config.order_type}")
        assert config.pair is not None
        order_result = await ctx.trading.place_market_order(
            pair=config.pair,
            side=config.side,
            amount=config.amount,
        )
        return await _format(config, order_result, ctx.trading)


async def _format(
    config: ActionConfig, order_result: dict[str, Any], trading: KrakenTrading
) -> str:
    if not order_result:
        return f"skipped {config.pair}: no quote balance"
    vol_exec, price = await trading.get_filled_order_details(order_result.get("txid", []))
    vol_str = vol_exec or "??"
    price_str = f"${price:.2f}" if price else "??"
    amount_str = f"${config.amount:.2f}" if config.amount is not None else "all available"
    return f"{config.side} {vol_str} of {config.pair} for {amount_str} @ {price_str}"
