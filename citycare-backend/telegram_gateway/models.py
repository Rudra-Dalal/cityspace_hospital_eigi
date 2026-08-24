"""Data models and session key helpers for Telegram Patient Assistant."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_session_key(chat_id: int, thread_id: Optional[int] = None, chat_type: str = "private") -> str:
    """Generate deterministic session key: tg:private:<chat_id>:<thread_id-or-0>."""
    t_id = thread_id or 0
    return f"tg:{chat_type}:{chat_id}:{t_id}"


class TelegramFlowType(str, Enum):
    IDLE = "idle"
    BOOKING = "booking"
    REGISTRATION = "registration"
    LINKING = "linking"
    CHAT = "chat"


class TelegramIdentity(BaseModel):
    telegram_user_id: int
    telegram_chat_id: int
    patient_id: Optional[str] = None
    verified: bool = False
    linked_at: Optional[datetime] = None
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    consent: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramSession(BaseModel):
    session_key: str
    telegram_user_id: int
    chat_id: int
    thread_id: Optional[int] = None
    patient_id: Optional[str] = None
    current_flow: str = TelegramFlowType.IDLE.value
    flow_step: Optional[str] = None
    flow_data: Dict[str, Any] = Field(default_factory=dict)
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramOtpToken(BaseModel):
    otp_id: str
    telegram_user_id: int
    target_type: str  # "email" | "mobile"
    target_value: str
    otp_hash: str
    attempts: int = 0
    max_attempts: int = 3
    purpose: str  # "link_account" | "register_patient"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountActivationToken(BaseModel):
    token_hash: str
    patient_id: str
    purpose: str = "password_setup"
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramIdempotencyStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TelegramIdempotency(BaseModel):
    update_id: int
    status: str = TelegramIdempotencyStatus.RECEIVED.value
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    error: Optional[str] = None
