"""Identity mapping, 1-to-1 account linking, and OTP management."""

import hashlib
import random
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.database import get_database
from app.cruds import user_crud
from telegram_gateway.models import TelegramIdentity, TelegramOtpToken
from telegram_gateway.otp_service import get_otp_delivery_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _hash_otp(raw_otp: str, salt: str = "citycare_tg_otp") -> str:
    """Salted SHA-256 hash of OTP code."""
    settings = get_settings()
    combined = f"{settings.secret_key}:{salt}:{raw_otp}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


class IdentityManager:
    """Resolves and links 1-to-1 Telegram identity to patient record."""

    @staticmethod
    async def resolve_identity(telegram_user_id: int) -> Tuple[Optional[TelegramIdentity], Optional[Dict[str, Any]]]:
        """
        Resolve Telegram identity and linked patient user document.
        Returns (identity, patient_user_doc).
        """
        db = get_database()
        id_doc = await db.telegram_identities.find_one({"telegram_user_id": telegram_user_id})
        if not id_doc:
            return None, None

        identity = TelegramIdentity(**id_doc)
        patient = None
        if identity.patient_id and identity.verified:
            patient = await user_crud.get_user_by_id(identity.patient_id)
            if patient and patient.get("is_active") is False:
                patient = None  # Block deactivated patient

        return identity, patient

    @staticmethod
    async def issue_otp(
        telegram_user_id: int,
        target_type: str,
        target_value: str,
        purpose: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Generate a 6-digit random code, store its salted hash, and dispatch via OtpDeliveryService.
        """
        settings = get_settings()
        db = get_database()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.telegram_otp_ttl_minutes)

        # Invalidate existing active OTPs for this user & purpose
        await db.telegram_otp_tokens.delete_many({
            "telegram_user_id": telegram_user_id,
            "purpose": purpose,
        })

        # Generate 6-digit code
        raw_code = f"{random.randint(100000, 999999)}"
        otp_h = _hash_otp(raw_code)
        otp_id = secrets.token_urlsafe(16)

        token_doc = TelegramOtpToken(
            otp_id=otp_id,
            telegram_user_id=telegram_user_id,
            target_type=target_type,
            target_value=target_value,
            otp_hash=otp_h,
            attempts=0,
            max_attempts=settings.telegram_otp_max_attempts,
            purpose=purpose,
            metadata=metadata or {},
            expires_at=expires_at,
            created_at=now,
        )

        await db.telegram_otp_tokens.insert_one(token_doc.model_dump())

        # Dispatch via configured OTP service (email / SMS / test)
        service = get_otp_delivery_service()
        delivered = await service.send_otp(
            target_type=target_type,
            target_value=target_value,
            otp_code=raw_code,
            purpose=purpose,
        )
        return delivered

    @staticmethod
    async def verify_otp(
        telegram_user_id: int,
        raw_code: str,
        purpose: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Verify an OTP against stored hash.
        Enforces maximum attempt limits and TTL expiry.
        Returns (is_valid, metadata_dict, error_message).
        """
        db = get_database()
        now = datetime.now(timezone.utc)

        token_doc = await db.telegram_otp_tokens.find_one({
            "telegram_user_id": telegram_user_id,
            "purpose": purpose,
            "expires_at": {"$gt": now},
        })

        if not token_doc:
            return False, None, "Verification code has expired or was not requested. Please request a new code."

        if token_doc.get("attempts", 0) >= token_doc.get("max_attempts", 3):
            await db.telegram_otp_tokens.delete_one({"_id": token_doc["_id"]})
            return False, None, "Too many incorrect attempts. Verification code invalidated. Please request a new code."

        entered_h = _hash_otp(raw_code.strip())
        if entered_h != token_doc["otp_hash"]:
            new_attempts = token_doc.get("attempts", 0) + 1
            remaining = token_doc.get("max_attempts", 3) - new_attempts
            await db.telegram_otp_tokens.update_one(
                {"_id": token_doc["_id"]},
                {"$set": {"attempts": new_attempts}},
            )
            if remaining <= 0:
                await db.telegram_otp_tokens.delete_one({"_id": token_doc["_id"]})
                return False, None, "Too many incorrect attempts. Code invalidated."
            return False, None, f"Incorrect verification code. {remaining} attempt(s) remaining."

        # Success: consume token
        await db.telegram_otp_tokens.delete_one({"_id": token_doc["_id"]})
        return True, token_doc.get("metadata", {}), ""

    @staticmethod
    async def link_patient(
        telegram_user_id: int,
        telegram_chat_id: int,
        patient_id: str,
        consent: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """
        Link Telegram user ID to Patient ID (1-to-1 bidirectional mapping).
        Returns (success, message).
        """
        db = get_database()
        now = datetime.now(timezone.utc)

        # 1. Check if Telegram account is already linked to another patient
        existing_tg = await db.telegram_identities.find_one({"telegram_user_id": telegram_user_id})
        if existing_tg and existing_tg.get("patient_id") and existing_tg["patient_id"] != patient_id:
            return False, "This Telegram account is already linked to another patient record."

        # 2. Check if patient is already linked to another Telegram account
        existing_patient = await db.telegram_identities.find_one({"patient_id": patient_id})
        if existing_patient and existing_patient.get("telegram_user_id") != telegram_user_id:
            return False, "This patient account is already linked to another Telegram user."

        payload: Dict[str, Any] = {
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "patient_id": patient_id,
            "verified": True,
            "linked_at": now,
            "last_seen_at": now,
            "updated_at": now,
        }
        if consent:
            payload["consent"] = consent

        try:
            await db.telegram_identities.update_one(
                {"telegram_user_id": telegram_user_id},
                {
                    "$set": payload,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            logger.info("Linked Telegram user %s to patient %s", telegram_user_id, patient_id)
            return True, "Account successfully linked!"
        except DuplicateKeyError:
            return False, "Account linking conflict: mapping already exists."

    @staticmethod
    async def revoke_identity(telegram_user_id: int) -> bool:
        """Unlink patient identity from Telegram user."""
        db = get_database()
        now = datetime.now(timezone.utc)
        res = await db.telegram_identities.update_one(
            {"telegram_user_id": telegram_user_id},
            {
                "$set": {
                    "patient_id": None,
                    "verified": False,
                    "linked_at": None,
                    "updated_at": now,
                }
            },
        )
        return res.modified_count > 0
