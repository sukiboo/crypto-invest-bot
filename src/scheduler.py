import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.schemas import ActionConfig

logger = logging.getLogger(__name__)

CRON_DOW = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def describe_schedule(cron: str, next_run: datetime | None = None) -> str:
    """Compact human cadence for a cron expression (e.g. 'daily 15:47', 'Mon 09:00',
    'every 15m'). Falls back to the next run time, then to the raw cron, so the label
    is never misleading for shapes the simplifier doesn't recognize."""
    m, h, dom, mon, dow = cron.split()
    if m.startswith("*/") and (h, dom, mon, dow) == ("*", "*", "*", "*"):
        return f"every {m[2:]}m"
    if h.startswith("*/") and m.isdigit() and (dom, mon, dow) == ("*", "*", "*"):
        return f"every {h[2:]}h"
    if m.isdigit() and h.isdigit():
        t = f"{int(h):02d}:{int(m):02d}"
        if (dom, mon, dow) == ("*", "*", "*"):
            return f"daily {t}"
        if dow.isdigit() and int(dow) in CRON_DOW and (dom, mon) == ("*", "*"):
            return f"{CRON_DOW[int(dow)]} {t}"
        if dom.isdigit() and (mon, dow) == ("*", "*"):
            return f"day {int(dom)} {t}"
    if next_run is not None:
        return f"next {next_run:%b %d %H:%M}"
    return cron


class JobScheduler:
    """Async job scheduler with cron expression support."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._jobs: dict[str, str] = {}  # action name -> job id

    def add_action(
        self,
        action: ActionConfig,
        callback: Callable[[ActionConfig], Awaitable[Any]],
    ) -> str:
        try:
            trigger = CronTrigger.from_crontab(action.schedule)
        except ValueError as e:
            logger.error(
                "Invalid cron expression '%s' for action '%s': %s", action.schedule, action.name, e
            )
            raise

        job = self.scheduler.add_job(
            callback,
            trigger=trigger,
            args=[action],
            id=action.name,
            name=action.name,
            replace_existing=True,
        )
        self._jobs[action.name] = job.id
        logger.info("Scheduled action '%s' with cron '%s'", action.name, action.schedule)
        return job.id

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started with %d jobs", len(self._jobs))

    def shutdown(self, wait: bool = True) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler shutdown")

    def get_next_run_times(self) -> dict[str, datetime | None]:
        return {job.name: job.next_run_time for job in self.scheduler.get_jobs()}
