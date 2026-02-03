import logging
from collections.abc import Awaitable, Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.schemas import ActionConfig

logger = logging.getLogger(__name__)


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
        """
        Schedule an action to run on its cron schedule.

        Args:
            action: The action configuration
            callback: Async function to call when triggered

        Returns:
            The job ID
        """
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
        logger.info(
            "Scheduled action '%s' with cron '%s'",
            action.name,
            action.schedule,
        )

        return job.id

    def remove_action(self, action_name: str) -> bool:
        job_id = self._jobs.get(action_name)
        if job_id:
            self.scheduler.remove_job(job_id)
            del self._jobs[action_name]
            logger.info("Removed action '%s' from scheduler", action_name)
            return True
        return False

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started with %d jobs", len(self._jobs))

    def shutdown(self, wait: bool = True) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler shutdown")

    def get_next_run_times(self) -> dict[str, str]:
        result = {}
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            result[job.name] = next_run.isoformat() if next_run else "not scheduled"
        return result
