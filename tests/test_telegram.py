import pytest

from src.notifications.telegram import TelegramNotifier


@pytest.fixture
def notifier(mock_telegram_bot, mocker):
    mocker.patch("src.notifications.telegram.Bot", return_value=mock_telegram_bot)
    return TelegramNotifier(bot_token="test-token", user_id="12345")


class TestSendMessage:
    async def test_escapes_html_entities(self, notifier, mock_telegram_bot):
        await notifier.send_message("<script>alert('xss')</script>", monospace=True)

        call_args = mock_telegram_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert "&lt;script&gt;" in text
        assert "&lt;/script&gt;" in text
        assert "'" not in text or "&#x27;" in text or text.count("'") == text.count("&#x27;")

    async def test_preserves_newlines_in_monospace(self, notifier, mock_telegram_bot):
        await notifier.send_message("line1\nline2", monospace=True)

        call_args = mock_telegram_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert "\n" in text

    async def test_monospace_uses_code_tags(self, notifier, mock_telegram_bot):
        await notifier.send_message("test message", monospace=True)

        call_args = mock_telegram_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert text.startswith("<code>")
        assert text.endswith("</code>")
        assert call_args.kwargs["parse_mode"] == "HTML"

    async def test_non_monospace_no_formatting(self, notifier, mock_telegram_bot):
        await notifier.send_message("test message", monospace=False)

        call_args = mock_telegram_bot.send_message.call_args
        assert call_args.kwargs["text"] == "test message"
        assert call_args.kwargs["parse_mode"] is None


class TestMessageTypes:
    async def test_send_update_adds_checkmark(self, notifier, mock_telegram_bot):
        await notifier.send_update("task done")

        call_args = mock_telegram_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert "✔️" in text
        assert call_args.kwargs["disable_notification"] is True

    async def test_send_alert_adds_error_emoji(self, notifier, mock_telegram_bot):
        await notifier.send_alert("something failed")

        call_args = mock_telegram_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert "❌" in text
        assert call_args.kwargs["disable_notification"] is False

    async def test_send_info_adds_light_emoji(self, notifier, mock_telegram_bot):
        await notifier.send_info("bot started")

        call_args = mock_telegram_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert "🔆" in text
        assert call_args.kwargs["disable_notification"] is False

    async def test_quiet_alert_skips_send(self, notifier, mock_telegram_bot):
        result = await notifier.send_alert("runway ok", quiet=True)

        assert result is True
        mock_telegram_bot.send_message.assert_not_called()

    async def test_loud_alert_still_sends_when_quiet_false(self, notifier, mock_telegram_bot):
        await notifier.send_alert("runway low", quiet=False)

        mock_telegram_bot.send_message.assert_called_once()
