import functools
import logging
from typing import Any, Callable, TypeVar

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TelegramNotifier:
    """Async Telegram notification service."""

    def __init__(self, bot_token: str, user_id: str) -> None:
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set!")
        if not user_id:
            raise ValueError("TELEGRAM_USER_ID is not set!")

        self.bot = Bot(token=bot_token)
        self.user_id = user_id

    async def send_message(self, message: str, silent: bool = False) -> bool:
        """
        Send a message to the configured user.

        Args:
            message: The message to send
            silent: If True, send without notification sound

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=self.user_id,
                text=message,
                disable_notification=silent,
            )
            return True
        except TelegramError as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False

    async def send_update(self, title: str, details: str = "") -> bool:
        """Send a formatted update message."""
        message = f"✅ {title}"
        if details:
            message += f"\n\n{details}"
        return await self.send_message(message, silent=True)

    async def send_alert(self, title: str, details: str = "") -> bool:
        """Send a formatted alert/error message."""
        message = f"🚨 {title}"
        if details:
            message += f"\n\n{details}"
        return await self.send_message(message, silent=False)


def notify_on_error(notifier: TelegramNotifier) -> Callable[[F], F]:
    """
    Decorator factory to catch exceptions and send Telegram alerts.

    Usage:
        @notify_on_error(telegram_notifier)
        async def my_function():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {type(e).__name__}: {e}"
                logger.exception(error_msg)
                await notifier.send_alert("Bot Error", error_msg)
                raise

        return wrapper  # type: ignore

    return decorator
