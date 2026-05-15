from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.actions.base import Action, ActionContext
from src.actions.utils import BuyForecast, upcoming_buys_by_quote
from src.schemas import ActionConfig


@dataclass
class RunwayLine:
    quote: str
    spot: float
    earn: float
    required: float
    items: BuyForecast

    @property
    def total(self) -> float:
        return self.spot + self.earn

    @property
    def ok(self) -> bool:
        return self.total >= self.required


class CheckRunwayAction(Action):
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> None:
        days = config.days
        assert days is not None
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        by_quote = await upcoming_buys_by_quote(ctx.settings.actions, ctx.kraken_client, now, end)
        balance = await ctx.kraken_client.get_balance()
        # Bonded/vault allocations are excluded for now — Kraken Vault is read-only
        # via API (Allocate/Deallocate rejected with "access restricted"), so the
        # bot can't auto-unstake when runway is short. Counting it as available
        # would falsely report "ok" when manual UI unstaking is actually required.
        # earn_by_asset = await ctx.earn.get_allocations_by_asset()

        lines: list[RunwayLine] = []
        for quote, items in by_quote.items():
            spot = await ctx.kraken_client.get_asset_balance(quote, balance)
            earn = 0.0
            # earn = sum(
            #     earn_by_asset.get(variant, 0.0) for variant in (quote, f"X{quote}", f"Z{quote}")
            # )
            lines.append(
                RunwayLine(
                    quote=quote,
                    spot=spot,
                    earn=earn,
                    required=sum(amt * c for _, amt, c in items),
                    items=items,
                )
            )

        all_ok = all(line.ok for line in lines)
        await ctx.telegram.send_alert(_format(days, lines, all_ok), quiet=all_ok)
        return None


def _format(days: int, lines: list[RunwayLine], all_ok: bool) -> str:
    if not lines:
        return f"{days}d runway: no buy actions scheduled"
    out = [f"{days}d runway {'ok' if all_ok else 'low'}", "Balance"]
    for line in lines:
        cmp = ">" if line.ok else "<"
        out.append(f"  {line.total:.2f} {line.quote} {cmp} {line.required:.2f} {line.quote}")
    out.append("Actions")
    for line in lines:
        for n, amt, c in line.items:
            out.append(f"  {n}: {c} x {amt:.2f} {line.quote} = {amt * c:.2f} {line.quote}")
    return "\n".join(out)
