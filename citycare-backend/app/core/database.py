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
    Old single-doctor index (date, slot) is replaced by the multi-tenant index
    (hospital_id, doctor_id, date, slot) WHERE status="booked".
    """
    db = get_database()

    # Users — unique email
    await db.users.create_index("email", unique=True, name="uniq_user_email")

    # Hospitals — unique name+city composite (advisory, non-blocking)
    try:
        await db.hospitals.create_index(
            [("name", 1), ("city", 1)],
            unique=True,
            name="uniq_hospital_name_city",
        )
    except Exception:
        pass  # Index may already exist from prior run

    # Appointments — drop legacy single-doctor index if it exists, then create multi-tenant one
    try:
        await db.appointments.drop_index("uniq_booked_date_slot")
        logger.info("Dropped legacy single-doctor appointment index")
    except Exception:
        pass  # Doesn't exist — that's fine

    await db.appointments.create_index(
        [("hospital_id", 1), ("doctor_id", 1), ("date", 1), ("slot", 1)],
        unique=True,
        partialFilterExpression={"status": "booked"},
        name="uniq_booked_hospital_doctor_date_slot",
    )
    await db.prescriptions.create_index("appointment_id", unique=True, name="uniq_prescription_appointment")
    await db.prescriptions.create_index([("patient_id", 1), ("created_at", -1)], name="prescription_patient_recent")
    await db.prescription_vectors.create_index([("patient_id", 1), ("prescription_id", 1)], name="prescription_vector_patient")
    await db.handbook_chunks.create_index(
        [("document", 1), ("version", 1), ("chunk_index", 1)],
        unique=True,
        name="uniq_handbook_doc_version_chunk",
    )

    logger.info("MongoDB indexes ensured (multi-tenant appointment index active)")
