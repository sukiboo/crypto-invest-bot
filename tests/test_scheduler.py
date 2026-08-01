from datetime import datetime

import pytest

from src.scheduler import JobScheduler
from src.schemas import ActionConfig


@pytest.fixture
def scheduler():
    return JobScheduler()


@pytest.fixture
def sample_action():
    return ActionConfig(
        name="Buy ETH",
        type="order",
        schedule="0 12 * * *",
        pair="ETHUSD",
        amount=100.0,
    )


# APScheduler inspects callback signatures, so we need a real async function
async def dummy_callback(action: ActionConfig):
    pass


class TestAddAction:
    def test_creates_job_with_cron_trigger(self, scheduler, sample_action):
        job_id = scheduler.add_action(sample_action, dummy_callback)

        assert job_id == "Buy ETH"
        assert "Buy ETH" in scheduler._jobs

    def test_tracks_job_id(self, scheduler, sample_action):
        scheduler.add_action(sample_action, dummy_callback)

        assert scheduler._jobs["Buy ETH"] == "Buy ETH"

    def test_invalid_cron_raises_error(self, scheduler):
        action = ActionConfig(
            name="Bad Action",
            type="order",
            schedule="invalid cron",
            pair="ETHUSD",
            amount=100.0,
        )

        with pytest.raises(ValueError):
            scheduler.add_action(action, dummy_callback)


class TestGetNextRunTimes:
    async def test_returns_datetimes(self, scheduler, sample_action):
        scheduler.add_action(sample_action, dummy_callback)
        scheduler.start()

        next_runs = scheduler.get_next_run_times()

        assert "Buy ETH" in next_runs
        # bot._format_schedule sorts on .time(), so these must stay datetimes.
        assert isinstance(next_runs["Buy ETH"], datetime)

        scheduler.shutdown()
