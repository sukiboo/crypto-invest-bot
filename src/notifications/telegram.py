import html
import logging

from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Async Telegram notification service."""

    def __init__(self, bot_token: str, user_id: str) -> None:
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set!")
        if not user_id:
            raise ValueError("TELEGRAM_USER_ID is not set!")

        self.bot = Bot(token=bot_token)
        self.user_id = user_id

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(TelegramError),
        reraise=True,
    )
    async def _send(self, text: str, silent: bool, parse_mode: str | None) -> None:
        await self.bot.send_message(
            chat_id=self.user_id,
            text=text,
            disable_notification=silent,
            parse_mode=parse_mode,
        )

    async def send_message(
        self, message: str, silent: bool = False, monospace: bool = False
    ) -> bool:
        if monospace:
            escaped = html.escape(message)
            for sep in ("\r\n", "\n", "\r"):
                escaped = escaped.replace(sep, "<br/>")
            text = f"<code>{escaped}</code>"
            parse_mode = "HTML"
        else:
            text = message
            parse_mode = None

        try:
            await self._send(text, silent, parse_mode)
            return True
        except TelegramError as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False

    async def send_update(self, message: str) -> bool:
        """Silent notification for routine updates."""
        return await self.send_message(f"✔️ {message}", silent=True, monospace=True)

    async def send_info(self, message: str) -> bool:
        """Non-silent notification for important info (e.g., bot started)."""
        return await self.send_message(f"🔆 {message}", silent=False, monospace=True)

    async def send_alert(self, message: str) -> bool:
        return await self.send_message(f"❌ {message}", silent=False, monospace=True)
