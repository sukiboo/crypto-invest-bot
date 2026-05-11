from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from src.actions._helpers import upcoming_buys_by_quote
from src.actions.base import Action, ActionContext
from src.schemas import ActionConfig

ReserveOp = Literal["stake", "unstake", "skip"]


@dataclass
class Rebalance:
    asset: str
    target: float
    spot: float
    pending: float
    bonded: float
    op: ReserveOp
    amount: float


def decide(target: float, spot: float, pending: float, bonded: float) -> tuple[ReserveOp, float]:
    available = spot + pending
    if available < target:
        deficit = target - available
        if deficit > bonded:
            raise ValueError(f"Cannot unstake {deficit:.2f}: only {bonded:.2f} bonded")
        return "unstake", deficit
    if available > target and spot > 0:
        return "stake", min(available - target, spot)
    return "skip", 0.0


class MaintainReserveAction(Action):
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> str:
        asset = config.asset
        days = config.days
        strategy_type = config.strategy
        assert asset is not None and days is not None and strategy_type is not None

        strategy = await ctx.earn.find_strategy(asset, strategy_type)
        if not strategy:
            raise ValueError(f"No matching '{strategy_type}' strategy for {asset}")
        strategy_id = strategy["id"]

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        by_quote = await upcoming_buys_by_quote(ctx.settings.actions, ctx.kraken_client, now, end)
        target = sum(amt * c for _, amt, c in by_quote.get(asset, []))

        balance = await ctx.kraken_client.get_balance()
        spot = await ctx.kraken_client.get_asset_balance(asset, balance)
        holdings = await ctx.earn.get_strategy_holdings(strategy_id)

        op, amount = decide(target, spot, holdings["pending_unstake"], holdings["bonded"])
        if op == "unstake":
            await ctx.earn.deallocate(strategy_id, amount)
        elif op == "stake":
            await ctx.earn.allocate(strategy_id, amount, asset)

        return _format(
            Rebalance(
                asset=asset,
                target=target,
                spot=spot,
                pending=holdings["pending_unstake"],
                bonded=holdings["bonded"],
                op=op,
                amount=amount,
            )
        )


def _format(r: Rebalance) -> str:
    available = r.spot + r.pending
    if r.op == "skip":
        return f"skip {r.asset} (target={r.target:.2f}, available={available:.2f})"
    return (
        f"{r.op} {r.amount:.2f} {r.asset} "
        f"(target={r.target:.2f}, spot={r.spot:.2f}, "
        f"pending={r.pending:.2f}, bonded={r.bonded:.2f})"
    )
