"""Persistent Telegram session and workflow state manager backed by MongoDB."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from app.core.config import get_settings
from app.core.database import get_database
from telegram_gateway.models import TelegramFlowType, TelegramSession, get_session_key
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages persistent Telegram sessions with deterministic keys and TTL expiration."""

    @staticmethod
    async def get_or_create_session(
        telegram_user_id: int,
        chat_id: int,
        thread_id: Optional[int] = None,
        chat_type: str = "private",
        patient_id: Optional[str] = None,
    ) -> TelegramSession:
        """Fetch active session or initialize new one with configured TTL."""
        settings = get_settings()
        session_key = get_session_key(chat_id=chat_id, thread_id=thread_id, chat_type=chat_type)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.telegram_session_ttl_minutes)

        db = get_database()
        doc = await db.telegram_sessions.find_one({"session_key": session_key})

        if doc:
            # Refresh activity timestamp and expiration
            update_fields: Dict[str, Any] = {
                "last_activity_at": now,
                "expires_at": expires_at,
                "updated_at": now,
            }
            if patient_id and not doc.get("patient_id"):
                update_fields["patient_id"] = patient_id
                doc["patient_id"] = patient_id

            await db.telegram_sessions.update_one(
                {"session_key": session_key},
                {"$set": update_fields},
            )
            doc["last_activity_at"] = now
            doc["expires_at"] = expires_at
            return TelegramSession(**doc)

        # Create new session
        new_session = TelegramSession(
            session_key=session_key,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            thread_id=thread_id,
            patient_id=patient_id,
            current_flow=TelegramFlowType.IDLE.value,
            flow_step=None,
            flow_data={},
            last_activity_at=now,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        await db.telegram_sessions.insert_one(new_session.model_dump())
        return new_session

    @staticmethod
    async def update_flow(
        session_key: str,
        current_flow: str,
        flow_step: Optional[str] = None,
        flow_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update flow state and merged flow data."""
        settings = get_settings()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.telegram_session_ttl_minutes)
        db = get_database()

        update_payload: Dict[str, Any] = {
            "current_flow": current_flow,
            "flow_step": flow_step,
            "last_activity_at": now,
            "expires_at": expires_at,
            "updated_at": now,
        }
        if flow_data is not None:
            update_payload["flow_data"] = flow_data

        await db.telegram_sessions.update_one(
            {"session_key": session_key},
            {"$set": update_payload},
        )

    @staticmethod
    async def clear_flow(session_key: str) -> None:
        """Clear active workflow state, returning session to idle while keeping patient_id."""
        settings = get_settings()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.telegram_session_ttl_minutes)
        db = get_database()

        await db.telegram_sessions.update_one(
            {"session_key": session_key},
            {
                "$set": {
                    "current_flow": TelegramFlowType.IDLE.value,
                    "flow_step": None,
                    "flow_data": {},
                    "last_activity_at": now,
                    "expires_at": expires_at,
                    "updated_at": now,
                }
            },
        )

    @staticmethod
    async def set_patient_id(session_key: str, patient_id: str) -> None:
        """Associate verified patient ID with active session."""
        now = datetime.now(timezone.utc)
        db = get_database()
        await db.telegram_sessions.update_one(
            {"session_key": session_key},
            {"$set": {"patient_id": patient_id, "updated_at": now}},
        )

    @staticmethod
    async def get_session(session_key: str) -> Optional[TelegramSession]:
        """Retrieve existing session by key without extending TTL."""
        db = get_database()
        doc = await db.telegram_sessions.find_one({"session_key": session_key})
        if doc:
            return TelegramSession(**doc)
        return None
