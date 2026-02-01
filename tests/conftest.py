from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_kraken_client(mocker):
    client = mocker.Mock()
    client._request = AsyncMock()
    client.get_balance = AsyncMock(return_value={"ETH": "1.5", "XBT": "0.1"})
    return client


@pytest.fixture
def mock_telegram_bot(mocker):
    bot = mocker.Mock()
    bot.send_message = AsyncMock()
    return bot
