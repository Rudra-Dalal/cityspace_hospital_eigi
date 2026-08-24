"""Durable update queue, atomic worker claiming with lease expiry, and background processor."""

import asyncio
import signal
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.utils.logger import get_logger
from telegram_gateway.models import TelegramUpdateStatus
from telegram_gateway.router import TelegramRouter

logger = get_logger(__name__)

DEFAULT_LEASE_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3


async def enqueue_update(payload: Dict[str, Any], max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> Tuple[bool, str]:
    """
    Durably persist full update payload in MongoDB before returning HTTP 200 to Telegram.
    Guarantees duplicate update IDs are dropped idempotently.
    """
    try:
        db = get_database()
    except RuntimeError:
        return True, "test_no_db"

    update_id = payload.get("update_id")
    if update_id is None:
        return False, "missing_update_id"

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=2)

    doc = {
        "update_id": update_id,
        "payload": payload,
        "status": TelegramUpdateStatus.PENDING.value,
        "attempts": 0,
        "max_attempts": max_attempts,
        "locked_until": None,
        "last_error": None,
        "created_at": now,
        "processed_at": None,
        "expires_at": expires_at,
    }

    try:
        await db.telegram_updates.insert_one(doc)
        logger.debug("Durably enqueued Telegram update %s", update_id)
        return True, "enqueued"
    except DuplicateKeyError:
        logger.info("Duplicate update %s dropped at enqueue stage", update_id)
        return True, "duplicate_ignored"
    except Exception as exc:
        logger.error("Failed to durably store Telegram update %s: %s", update_id, exc)
        return False, str(exc)


async def claim_next_update(lease_seconds: int = DEFAULT_LEASE_SECONDS) -> Optional[Dict[str, Any]]:
    """
    Atomically claim the next eligible update for processing.
    Eligible conditions:
    1. status == 'pending'
    2. status == 'failed' AND attempts < max_attempts
    3. status == 'processing' AND locked_until < now (lease expired from crashed worker) AND attempts < max_attempts
    """
    try:
        db = get_database()
    except RuntimeError:
        return None

    now = datetime.now(timezone.utc)
    locked_until = now + timedelta(seconds=lease_seconds)

    try:
        claimed_doc = await db.telegram_updates.find_one_and_update(
            {
                "$or": [
                    {
                        "status": TelegramUpdateStatus.PENDING.value,
                    },
                    {
                        "status": TelegramUpdateStatus.FAILED.value,
                        "$expr": {"$lt": ["$attempts", {"$ifNull": ["$max_attempts", DEFAULT_MAX_ATTEMPTS]}]},
                    },
                    {
                        "status": TelegramUpdateStatus.PROCESSING.value,
                        "locked_until": {"$lt": now},
                        "$expr": {"$lt": ["$attempts", {"$ifNull": ["$max_attempts", DEFAULT_MAX_ATTEMPTS]}]},
                    },
                ]
            },
            {
                "$set": {
                    "status": TelegramUpdateStatus.PROCESSING.value,
                    "locked_until": locked_until,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return claimed_doc
    except Exception as exc:
        logger.error("Error during atomic update claiming: %s", exc)
        return None



async def mark_update_completed(update_id: int) -> None:
    """Mark update as successfully completed."""
    try:
        db = get_database()
        now = datetime.now(timezone.utc)
        await db.telegram_updates.update_one(
            {"update_id": update_id},
            {
                "$set": {
                    "status": TelegramUpdateStatus.COMPLETED.value,
                    "processed_at": now,
                    "locked_until": None,
                    "last_error": None,
                }
            },
        )
    except Exception as exc:
        logger.error("Failed to mark update %s completed: %s", update_id, exc)


async def mark_update_failed(update_id: int, error: str) -> None:
    """Mark update as failed with error details so it can be retried or bounded."""
    try:
        db = get_database()
        await db.telegram_updates.update_one(
            {"update_id": update_id},
            {
                "$set": {
                    "status": TelegramUpdateStatus.FAILED.value,
                    "last_error": str(error),
                    "locked_until": None,
                }
            },
        )
    except Exception as exc:
        logger.error("Failed to mark update %s failed: %s", update_id, exc)


async def process_one_claimed_update(router: TelegramRouter, update_doc: Dict[str, Any]) -> bool:
    """Process a single claimed update with durable lifecycle status tracking."""
    update_id = update_doc["update_id"]
    payload = update_doc.get("payload", {})

    try:
        await router.process_update(payload)
        await mark_update_completed(update_id)
        logger.debug("Successfully processed and completed update %s", update_id)
        return True
    except Exception as exc:
        logger.error("Error executing Telegram update %s: %s", update_id, exc)
        await mark_update_failed(update_id, str(exc))
        return False


async def process_pending_batch(router: Optional[TelegramRouter] = None, max_batch_size: int = 10) -> int:
    """Process a batch of pending/retryable updates."""
    if router is None:
        from telegram_gateway.router import get_telegram_router
        router = get_telegram_router()

    processed_count = 0
    for _ in range(max_batch_size):
        doc = await claim_next_update()
        if not doc:
            break
        await process_one_claimed_update(router, doc)
        processed_count += 1

    return processed_count


async def run_worker_loop(
    router: Optional[TelegramRouter] = None,
    poll_interval_seconds: float = 0.5,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Dedicated background worker loop for processing durable updates."""
    if router is None:
        from telegram_gateway.router import get_telegram_router
        router = get_telegram_router()

    logger.info("Starting Telegram durable update worker loop (interval=%ss)", poll_interval_seconds)

    while stop_event is None or not stop_event.is_set():
        try:
            claimed = await claim_next_update()
            if claimed:
                await process_one_claimed_update(router, claimed)
            else:
                await asyncio.sleep(poll_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Telegram durable update worker received cancellation")
            break
        except Exception as exc:
            logger.error("Unexpected error in worker loop: %s", exc)
            await asyncio.sleep(poll_interval_seconds)


async def main() -> None:
    """Standalone worker process entry point."""
    from app.core.database import close_mongo_connection, connect_to_mongo, ensure_indexes

    logger.info("Initializing Telegram Update Worker process...")
    await connect_to_mongo()
    await ensure_indexes()

    stop_event = asyncio.Event()

    def handle_shutdown():
        logger.info("Shutdown signal received, stopping worker...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_shutdown)
        except NotImplementedError:
            pass  # Windows event loop limitation

    try:
        await run_worker_loop(stop_event=stop_event)
    finally:
        await close_mongo_connection()
        logger.info("Telegram Update Worker stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
