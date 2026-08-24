"""Distributed MongoDB atomic rate limiter for Telegram gateway."""

import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from app.core.database import get_database
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MongoRateLimiter:
    """Atomic sliding/bucket rate limiter backed by MongoDB."""

    @staticmethod
    async def is_allowed(
        user_id: int,
        action: str = "msg",
        limit: int = 30,
        window_seconds: int = 60,
    ) -> bool:
        """
        Check and record an action attempt.
        Returns True if within limit, False if rate limited.
        """
        try:
            db = get_database()
        except RuntimeError:
            return True  # Fallback if DB not ready in tests

        current_window = int(time.time()) // window_seconds
        rate_key = f"tg_rl:{user_id}:{action}:{current_window}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=window_seconds * 2)

        try:
            result = await db.telegram_rate_limits.find_one_and_update(
                {"key": rate_key},
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {"expires_at": expires_at, "created_at": now},
                },
                upsert=True,
                return_document=True,
            )
            count = result.get("count", 1) if result else 1
            if count > limit:
                logger.warning("Rate limit exceeded for user %s on action '%s' (%s/%s)", user_id, action, count, limit)
                return False
            return True
        except Exception as exc:
            logger.error("Rate limiter database error: %s", exc)
            return True  # Fail open gracefully on DB error
