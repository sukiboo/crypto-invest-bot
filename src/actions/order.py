from typing import Any

from src.actions.base import Action, ActionContext
from src.kraken.trading import KrakenTrading
from src.schemas import ActionConfig


class OrderAction(Action):
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> str | None:
        if config.order_type != "market":
            raise ValueError(f"Unsupported order type: {config.order_type}")
        assert config.pair is not None
        order_result = await ctx.trading.place_market_order(
            pair=config.pair,
            side=config.side,
            amount=config.amount,
        )
        if order_result is None:
            return None
        return await _format(config, order_result, ctx.trading)


async def _format(
    config: ActionConfig, order_result: dict[str, Any], trading: KrakenTrading
) -> str:
    assert config.pair is not None
    base, quote = await trading.client.get_pair_symbols(config.pair)
    filled = await trading.get_filled_order(order_result.get("txid", []), config.side)

    if filled is None:
        amount_str = (
            f"{config.amount:.2f} {quote}"
            if config.amount is not None
            else f"all available {quote}"
        )
        return f"{config.side} ?? {base} for {amount_str} @ ??"

    # Report what actually hit the wallet: for buys, the base credit is net of the
    # base-side fee; for sells, the quote credit is net of the quote-side fee. The
    # effective price uses the same net side, so price × volume reconciles to the
    # gross paid/received.
    if config.side == "buy":
        vol = filled.gross_base - filled.fee_base
        amount = filled.gross_quote
    else:
        vol = filled.gross_base
        amount = filled.gross_quote - filled.fee_quote

    vol_str = f"{vol:.8f}".rstrip("0").rstrip(".") if vol > 0 else "??"
    price_str = f"{amount / vol:.2f} {quote}/{base}" if vol > 0 else "??"
    amount_str = (
        f"{config.amount:.2f} {quote}"
        if config.side == "buy" and config.amount is not None
        else f"{amount:.2f} {quote}"
    )
    return f"{config.side} {vol_str} {base} for {amount_str} @ {price_str}"
