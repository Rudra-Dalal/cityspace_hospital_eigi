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
    Partial unique index on (date, slot) for status=booked.
    Cancelling frees the slot while keeping the historical record.
    """
    db = get_database()
    await db.appointments.create_index(
        [("date", 1), ("slot", 1)],
        unique=True,
        partialFilterExpression={"status": "booked"},
        name="uniq_booked_date_slot",
    )
    await db.users.create_index("email", unique=True, name="uniq_user_email")
    logger.info("MongoDB indexes ensured (including partial unique booked date+slot)")
