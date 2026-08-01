import pytest
from pydantic import ValidationError

from src.schemas import ActionConfig, AppConfig


class TestActionConfig:
    def test_order_action_valid(self):
        action = ActionConfig(
            name="Buy ETH",
            type="order",
            schedule="0 12 * * *",
            pair="ETHUSD",
            amount=100.0,
        )
        assert action.pair == "ETHUSD"
        assert action.amount == 100.0

    def test_order_action_requires_pair(self):
        with pytest.raises(ValidationError, match="'pair' is required"):
            ActionConfig(
                name="Buy ETH",
                type="order",
                schedule="0 12 * * *",
                amount=100.0,
            )

    def test_order_action_requires_positive_amount(self):
        with pytest.raises(ValidationError, match="'amount' must be positive"):
            ActionConfig(
                name="Buy ETH",
                type="order",
                schedule="0 12 * * *",
                pair="ETHUSD",
                amount=0,
            )

    def test_order_action_rejects_negative_amount(self):
        with pytest.raises(ValidationError, match="'amount' must be positive"):
            ActionConfig(
                name="Buy ETH",
                type="order",
                schedule="0 12 * * *",
                pair="ETHUSD",
                amount=-50.0,
            )

    def test_earn_action_valid(self):
        action = ActionConfig(
            name="Stake ETH",
            type="earn",
            schedule="0 12 * * *",
            asset="ETH",
            strategy="bonded",
        )
        assert action.asset == "ETH"
        assert action.strategy == "bonded"

    def test_earn_action_requires_asset(self):
        with pytest.raises(ValidationError, match="'asset' is required"):
            ActionConfig(
                name="Stake ETH",
                type="earn",
                schedule="0 12 * * *",
                strategy="bonded",
            )

    def test_earn_action_requires_strategy(self):
        with pytest.raises(ValidationError, match="'strategy' is required"):
            ActionConfig(
                name="Stake ETH",
                type="earn",
                schedule="0 12 * * *",
                asset="ETH",
            )

    def test_earn_action_allows_none_amount(self):
        action = ActionConfig(
            name="Stake ETH",
            type="earn",
            schedule="0 12 * * *",
            asset="ETH",
            strategy="bonded",
            amount=None,
        )
        assert action.amount is None

    def test_earn_action_rejects_negative_amount(self):
        with pytest.raises(ValidationError, match="'amount' must be positive"):
            ActionConfig(
                name="Stake ETH",
                type="earn",
                schedule="0 12 * * *",
                asset="ETH",
                strategy="bonded",
                amount=-10.0,
            )

    def test_check_runway_action_valid(self):
        action = ActionConfig(
            name="Check runway",
            type="check_runway",
            schedule="0 12 * * *",
            days=7,
        )
        assert action.days == 7

    def test_check_runway_requires_days(self):
        with pytest.raises(ValidationError, match="'days' must be positive"):
            ActionConfig(
                name="Check runway",
                type="check_runway",
                schedule="0 12 * * *",
            )

    def test_check_runway_rejects_zero_days(self):
        with pytest.raises(ValidationError, match="'days' must be positive"):
            ActionConfig(
                name="Check runway",
                type="check_runway",
                schedule="0 12 * * *",
                days=0,
            )

    def test_check_runway_rejects_negative_days(self):
        with pytest.raises(ValidationError, match="'days' must be positive"):
            ActionConfig(
                name="Check runway",
                type="check_runway",
                schedule="0 12 * * *",
                days=-1,
            )


class TestAppConfig:
    def test_none_actions_defaults_to_empty_list(self):
        config = AppConfig(**{"bot_name": "test-bot", "actions": None})
        assert config.actions == []

    def test_missing_actions_defaults_to_empty_list(self):
        config = AppConfig(**{"bot_name": "test-bot"})
        assert config.actions == []

    def test_valid_actions_list(self):
        config = AppConfig(
            **{
                "bot_name": "test-bot",
                "actions": [
                    {
                        "name": "Buy ETH",
                        "type": "order",
                        "schedule": "0 12 * * *",
                        "pair": "ETHUSD",
                        "amount": 100.0,
                    }
                ],
            }
        )
        assert len(config.actions) == 1
        assert config.actions[0].name == "Buy ETH"
