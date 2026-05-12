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
    vol_exec, price, cost, fee = await trading.get_filled_order_details(
        order_result.get("txid", [])
    )
    assert config.pair is not None
    base, quote = await trading.client.get_pair_symbols(config.pair)
    # Buys use oflags=fcib, so the fee is deducted from the bought (base) asset.
    # Report the net amount credited and the effective per-unit price (cost / net_vol).
    if config.side == "buy" and vol_exec and fee is not None and cost is not None:
        net = float(vol_exec) - fee
        vol_str = f"{net:.8f}".rstrip("0").rstrip(".")
        price_str = f"{cost / net:.2f} {base}/{quote}" if net > 0 else "??"
    else:
        vol_str = vol_exec or "??"
        price_str = f"{price:.2f} {base}/{quote}" if price else "??"
    if config.amount is not None:
        amount_str = f"{config.amount:.2f} {quote}"
    elif cost is not None:
        amount_str = f"{cost:.2f} {quote}"
    else:
        amount_str = f"all available {quote}"
    return f"{config.side} {vol_str} {base} for {amount_str} @ {price_str}"
