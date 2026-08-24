import asyncio
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.utils.logger import get_logger
from telegram_gateway.router import TelegramRouter
from telegram_gateway.worker import enqueue_update, process_pending_batch

logger = get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Gateway"])
_router_instance: TelegramRouter = TelegramRouter()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> Dict[str, Any]:
    """
    Handle incoming updates from Telegram Bot API via Webhook.
    1. Validates X-Telegram-Bot-Api-Secret-Token header.
    2. Durably persists the full update payload in MongoDB.
    3. Triggers asynchronous worker processing.
    4. Returns HTTP 200 to Telegram only after durable persistence.
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

    if not isinstance(update_data, dict) or "update_id" not in update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing update_id in payload.",
        )

    # 1. Durably store update in MongoDB BEFORE returning HTTP 200
    saved, reason = await enqueue_update(update_data)
    if not saved:
        logger.error("Failed to durably enqueue Telegram update: %s", reason)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist update.",
        )

    # 2. Trigger asynchronous worker batch processing for near-instant execution
    background_tasks.add_task(process_pending_batch, _router_instance)

    # 3. Return HTTP 200 to Telegram
    return {"ok": True, "status": "persisted", "reason": reason}

