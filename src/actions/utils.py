from collections.abc import Iterable
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger

from src.kraken import KrakenClient
from src.schemas import ActionConfig

# (action_name, per-fire amount, fire count within the window)
BuyForecast = list[tuple[str, float, int]]


async def upcoming_buys_by_quote(
    actions: Iterable[ActionConfig],
    kraken_client: KrakenClient,
    now: datetime,
    end: datetime,
) -> dict[str, BuyForecast]:
    by_quote: dict[str, BuyForecast] = {}
    for a in actions:
        if a.type != "order" or a.side != "buy" or a.amount is None or a.pair is None:
            continue
        trigger = CronTrigger.from_crontab(a.schedule, timezone="UTC")
        count, prev = 0, now
        while (nxt := trigger.get_next_fire_time(prev, prev)) is not None and nxt <= end:
            count += 1
            prev = nxt
        if count:
            _, quote = await kraken_client.get_pair_symbols(a.pair)
            by_quote.setdefault(quote, []).append((a.name, a.amount, count))
    return by_quote
