from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.actions._helpers import upcoming_buys_by_quote
from src.actions.base import Action, ActionContext
from src.schemas import ActionConfig


@dataclass
class RunwayLine:
    quote: str
    balance: float
    required: float
    items: list[tuple[str, float, int]]

    @property
    def ok(self) -> bool:
        return self.balance >= self.required


class CheckRunwayAction(Action):
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> None:
        days = config.days
        assert days is not None
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        by_quote = await upcoming_buys_by_quote(ctx.settings.actions, ctx.kraken_client, now, end)
        balance = await ctx.kraken_client.get_balance()

        lines: list[RunwayLine] = []
        for quote, items in by_quote.items():
            bal = await ctx.kraken_client.get_asset_balance(quote, balance)
            lines.append(
                RunwayLine(
                    quote=quote,
                    balance=bal,
                    required=sum(amt * c for _, amt, c in items),
                    items=items,
                )
            )

        all_ok = all(line.ok for line in lines)
        await ctx.telegram.send_alert(_format(days, lines), quiet=all_ok)
        return None


def _format(days: int, lines: list[RunwayLine]) -> str:
    if not lines:
        return f"{days}d runway: no buy actions scheduled"
    if all(line.ok for line in lines):
        parts = [f"{line.quote} ${line.balance:.2f} >= ${line.required:.2f}" for line in lines]
        return f"{days}d runway ok: " + ", ".join(parts)
    out = [f"{days}d runway low:"]
    for line in lines:
        cmp = ">=" if line.ok else "<"
        out.append(f"  {line.quote}: ${line.balance:.2f} {cmp} ${line.required:.2f}")
        if not line.ok:
            for n, amt, c in line.items:
                out.append(f"    {n}: {c} x ${amt:.2f} = ${amt * c:.2f}")
    return "\n".join(out)
