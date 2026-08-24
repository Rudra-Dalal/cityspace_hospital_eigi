"""Async MongoDB connection via Motor."""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo() -> None:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db_name]
    # Verify connectivity early so startup failures are loud
    await _client.admin.command("ping")
    logger.info("Connected to MongoDB database '%s'", settings.mongodb_db_name)


async def close_mongo_connection() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database is not initialized. Call connect_to_mongo() first.")
    return _db


async def ensure_indexes() -> None:
    """
    Create/update all MongoDB indexes.
    All operations are idempotent and non-destructive.
    """
    db = get_database()

    # 1. Users
    await db.users.create_index("email", unique=True, name="uniq_user_email")
    await db.users.create_index(
        [("hospital_id", 1), ("role", 1), ("is_active", 1)],
        name="doctors_by_hospital",
    )
    await db.users.create_index(
        [("role", 1), ("specialization", 1), ("is_active", 1)],
        name="doctors_by_specialization",
    )

    # 2. Hospitals
    try:
        await db.hospitals.create_index(
            [("name", 1), ("city", 1)],
            unique=True,
            name="uniq_hospital_name_city",
        )
    except Exception as exc:
        logger.debug("Hospitals unique composite index exists or notice: %s", exc)

    await db.hospitals.create_index("status", name="hospital_status")

    # 3. Appointments
    try:
        await db.appointments.drop_index("uniq_booked_date_slot")
        logger.info("Dropped legacy single-doctor appointment index")
    except Exception:
        pass  # Legacy index does not exist

    await db.appointments.create_index(
        [("hospital_id", 1), ("doctor_id", 1), ("date", 1), ("slot", 1)],
        unique=True,
        partialFilterExpression={"status": "booked"},
        name="uniq_booked_hospital_doctor_date_slot",
    )
    await db.appointments.create_index(
        [("patient_id", 1), ("created_at", -1)],
        name="appointments_patient_recent",
    )
    await db.appointments.create_index(
        [("doctor_id", 1), ("date", 1), ("slot", 1)],
        name="appointments_doctor_date_slot",
    )

    # 4. Prescriptions
    await db.prescriptions.create_index("appointment_id", unique=True, name="uniq_prescription_appointment")
    await db.prescriptions.create_index([("patient_id", 1), ("created_at", -1)], name="prescription_patient_recent")
    await db.prescriptions.create_index([("doctor_id", 1), ("created_at", -1)], name="prescription_doctor_recent")

    # 5. RAG Vectors & Knowledge Chunks
    await db.prescription_vectors.create_index([("patient_id", 1), ("prescription_id", 1)], name="prescription_vector_patient")
    await db.handbook_chunks.create_index(
        [("document", 1), ("version", 1), ("chunk_index", 1)],
        unique=True,
        name="uniq_handbook_doc_version_chunk",
    )

    # 6. Telegram Identities (1-to-1 mapping)
    await db.telegram_identities.create_index("telegram_user_id", unique=True, name="uniq_telegram_user_id")
    try:
        await db.telegram_identities.create_index(
            "patient_id",
            unique=True,
            partialFilterExpression={"patient_id": {"$exists": True, "$type": "string"}},
            name="uniq_telegram_patient_id",
        )
    except Exception as exc:
        logger.debug("Telegram identities patient_id partial unique index notice: %s", exc)

    # 7. Telegram Sessions (Deterministic session key + TTL expiry)
    await db.telegram_sessions.create_index("session_key", unique=True, name="uniq_telegram_session_key")
    await db.telegram_sessions.create_index("expires_at", expireAfterSeconds=0, name="ttl_telegram_sessions")

    # 8. Telegram OTP Tokens (Salted hash + TTL expiry)
    await db.telegram_otp_tokens.create_index("otp_id", unique=True, name="uniq_telegram_otp_id")
    await db.telegram_otp_tokens.create_index("expires_at", expireAfterSeconds=0, name="ttl_telegram_otp_tokens")
    await db.telegram_otp_tokens.create_index([("telegram_user_id", 1), ("purpose", 1)], name="telegram_otp_user_purpose")

    # 9. Account Activation Tokens (One-time secure web password setup + TTL expiry)
    await db.account_activation_tokens.create_index("token_hash", unique=True, name="uniq_activation_token_hash")
    await db.account_activation_tokens.create_index("expires_at", expireAfterSeconds=0, name="ttl_activation_tokens")
    await db.account_activation_tokens.create_index("patient_id", name="activation_patient_id")

    # 10. Telegram Idempotency & Distributed Rate Limits
    await db.telegram_idempotency.create_index("update_id", unique=True, name="uniq_telegram_idempotency_update")
    await db.telegram_idempotency.create_index("expires_at", expireAfterSeconds=0, name="ttl_telegram_idempotency")
    await db.telegram_rate_limits.create_index("key", unique=True, name="uniq_telegram_rate_limit_key")
    await db.telegram_rate_limits.create_index("expires_at", expireAfterSeconds=0, name="ttl_telegram_rate_limits")

    # 11. Durable Telegram Incoming Updates
    await db.telegram_updates.create_index("update_id", unique=True, name="uniq_telegram_updates_id")
    await db.telegram_updates.create_index([("status", 1), ("locked_until", 1), ("attempts", 1)], name="idx_telegram_updates_queue")
    await db.telegram_updates.create_index("expires_at", expireAfterSeconds=0, name="ttl_telegram_updates")

    logger.info("MongoDB indexes ensured successfully.")


