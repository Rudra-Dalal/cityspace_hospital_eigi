"""Async Telegram Bot API transport adapter with retries and escaping."""

import asyncio
import re
from typing import Any, Dict, List, Optional, Union
import httpx

from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def escape_markdown(text: Optional[str]) -> str:
    """
    Escape special Markdown characters for Telegram v1/standard format.
    Characters: _ * ` [ ] ( ) ~ > # + - = | { } . !
    """
    if not text:
        return ""
    pattern = r"([_*`\[\]()~>#+\-=|{}.!])"
    return re.sub(pattern, r"\\\1", str(text))


class TelegramAdapter:
    """Async HTTP client wrapper for Telegram Bot API."""

    def __init__(self, bot_token: Optional[str] = None):
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = float(settings.telegram_request_timeout_seconds)

    async def _post(self, method: str, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None, retries: int = 3) -> Dict[str, Any]:
        """Perform an async HTTP POST request to Telegram API with exponential backoff."""
        url = f"{self.base_url}/{method}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if files:
                        resp = await client.post(url, data=data or {}, files=files)
                    else:
                        resp = await client.post(url, json=data or {})

                    result = resp.json()
                    if not result.get("ok"):
                        logger.warning("Telegram API error on %s: %s", method, result.get("description"))
                    return result
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning("Telegram network attempt %s/%s failed on %s: %s", attempt, retries, method, exc)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        logger.error("Telegram API call %s failed after %s retries: %s", method, retries, last_exc)
        return {"ok": False, "description": str(last_exc)}

    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "Markdown",
    ) -> Dict[str, Any]:
        """Send text message with optional inline keyboard."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._post("sendMessage", data=payload)

    async def edit_message_text(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "Markdown",
    ) -> Dict[str, Any]:
        """Edit an existing message text and keyboard."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._post("editMessageText", data=payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> Dict[str, Any]:
        """Acknowledge inline button click."""
        payload: Dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text
        return await self._post("answerCallbackQuery", data=payload)

    async def send_chat_action(self, chat_id: Union[int, str], action: str = "typing") -> Dict[str, Any]:
        """Send chat typing or document upload indicator."""
        return await self._post("sendChatAction", data={"chat_id": chat_id, "action": action})

    async def send_document(
        self,
        chat_id: Union[int, str],
        document: Union[str, bytes],
        filename: str = "prescription.pdf",
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send PDF document by URL or bytes."""
        if isinstance(document, str):
            # URL string
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "document": document,
            }
            if caption:
                payload["caption"] = caption
            return await self._post("sendDocument", data=payload)
        else:
            # Raw bytes
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            files = {"document": (filename, document, "application/pdf")}
            return await self._post("sendDocument", data=data, files=files)

    async def set_webhook(self, url: str, secret_token: Optional[str] = None) -> Dict[str, Any]:
        """Configure production webhook."""
        payload: Dict[str, Any] = {
            "url": url,
            "allowed_updates": ["message", "callback_query"],
        }
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._post("setWebhook", data=payload)

    async def delete_webhook(self) -> Dict[str, Any]:
        """Delete active webhook."""
        return await self._post("deleteWebhook")

    async def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> Dict[str, Any]:
        """Long poll for updates in local development mode."""
        payload: Dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        return await self._post("getUpdates", data=payload)


class FakeTelegramAdapter:
    """In-memory mock adapter used for fast, deterministic unit and integration tests."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []
        self.answered_callbacks: List[Dict[str, Any]] = []
        self.sent_documents: List[Dict[str, Any]] = []
        self.chat_actions: List[Dict[str, Any]] = []

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode="Markdown"):
        msg = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode,
            "message_id": len(self.sent_messages) + 1,
        }
        self.sent_messages.append(msg)
        return {"ok": True, "result": msg}

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
        msg = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode,
        }
        self.edited_messages.append(msg)
        return {"ok": True, "result": msg}

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        cb = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }
        self.answered_callbacks.append(cb)
        return {"ok": True, "result": True}

    async def send_chat_action(self, chat_id, action="typing"):
        self.chat_actions.append({"chat_id": chat_id, "action": action})
        return {"ok": True, "result": True}

    async def send_document(self, chat_id, document, filename="prescription.pdf", caption=None):
        doc = {
            "chat_id": chat_id,
            "document": document,
            "filename": filename,
            "caption": caption,
        }
        self.sent_documents.append(doc)
        return {"ok": True, "result": doc}

    async def set_webhook(self, url, secret_token=None):
        return {"ok": True, "result": True}

    async def delete_webhook(self):
        return {"ok": True, "result": True}

    async def get_updates(self, offset=None, timeout=30):
        return {"ok": True, "result": []}

    def clear(self):
        self.sent_messages.clear()
        self.edited_messages.clear()
        self.answered_callbacks.clear()
        self.sent_documents.clear()
        self.chat_actions.clear()

    @property
    def last_message(self) -> Optional[Dict[str, Any]]:
        return self.sent_messages[-1] if self.sent_messages else None
