"""Production Telegram webhook route with secret token validation."""

from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.core.config import get_settings
from telegram_gateway.router import TelegramRouter
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Gateway"])
_router_instance: TelegramRouter = TelegramRouter()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> Dict[str, bool]:
    """
    Handle incoming updates from Telegram Bot API via Webhook.
    Validates X-Telegram-Bot-Api-Secret-Token header.
    Dispatches update to background task to respond promptly to Telegram.
    """
    settings = get_settings()

    if not settings.telegram_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram gateway is currently disabled.",
        )

    # Secret token validation
    expected_secret = settings.telegram_webhook_secret
    if expected_secret:
        if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != expected_secret:
            logger.warning("Rejected Telegram webhook request with invalid secret token")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Telegram webhook secret token.",
            )

    try:
        update_data = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    # Enqueue background processing so HTTP response returns in <100ms
    background_tasks.add_task(_router_instance.process_update, update_data)
    return {"ok": True}
