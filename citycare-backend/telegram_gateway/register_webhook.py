"""CLI utility to register Telegram Webhook with Telegram Bot API."""

import asyncio
from typing import Any, Dict

from app.core.config import get_settings
from app.utils.logger import get_logger
from telegram_gateway.adapter import TelegramAdapter

logger = get_logger(__name__)


async def register_webhook(adapter: Any = None) -> Dict[str, Any]:
    """
    Register the configured production webhook URL and secret token with Telegram Bot API.
    Uses TELEGRAM_WEBHOOK_URL and TELEGRAM_WEBHOOK_SECRET from environment settings.
    """
    settings = get_settings()

    if not settings.telegram_enabled:
        logger.warning("TELEGRAM_ENABLED is false. Webhook registration skipped.")
        return {"ok": False, "description": "TELEGRAM_ENABLED is false"}

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN missing"}

    if not settings.telegram_webhook_url:
        logger.error("TELEGRAM_WEBHOOK_URL is not set.")
        return {"ok": False, "description": "TELEGRAM_WEBHOOK_URL missing"}

    if adapter is None:
        adapter = TelegramAdapter(bot_token=settings.telegram_bot_token)

    logger.info("Registering Telegram Webhook URL: %s", settings.telegram_webhook_url)

    result = await adapter.set_webhook(
        url=settings.telegram_webhook_url,
        secret_token=settings.telegram_webhook_secret,
    )

    if result.get("ok"):
        logger.info("Telegram Webhook successfully registered with Telegram Bot API: %s", result)
    else:
        logger.error("Telegram Webhook registration failed: %s", result)

    return result



def main():
    """CLI entry point for python -m telegram_gateway.register_webhook."""
    res = asyncio.run(register_webhook())
    print(f"Webhook Registration Result: {res}")


if __name__ == "__main__":
    main()
