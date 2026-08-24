"""CLI utility helpers — token resolution, auth, formatting, DB lifecycle."""

import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from jose import JWTError

from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo, get_database
from app.core.security import decode_access_token


# ---------------------------------------------------------------------------
# Token resolution
# ---------------------------------------------------------------------------

def resolve_token(args_token: Optional[str] = None) -> Optional[str]:
    """Return token from CLI --token arg or CITYCARE_JWT_TOKEN env var, or None."""
    if args_token:
        return args_token.strip()
    return os.environ.get("CITYCARE_JWT_TOKEN", "").strip() or None


# ---------------------------------------------------------------------------
# Authenticated user loader
# ---------------------------------------------------------------------------

async def load_current_user(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Decode JWT and fetch the user from MongoDB.
    Returns the user dict on success, or None if the token is missing/invalid/expired.
    Never raises — all errors are swallowed and None is returned.
    """
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    try:
        from bson import ObjectId
        from bson.errors import InvalidId
        db = get_database()
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            if user.get("is_active") is False:
                return None
            user["id"] = str(user["_id"])
        return user
    except (InvalidId, RuntimeError, Exception):
        return None


# ---------------------------------------------------------------------------
# DB lifecycle context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def db_context():
    """Async context manager that connects and cleanly closes MongoDB."""
    await connect_to_mongo()
    try:
        yield
    finally:
        await close_mongo_connection()


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def print_json(data: Any) -> None:
    """Serialize and print data as pretty JSON."""
    print(json.dumps(data, indent=2, default=str))


def print_table(rows: List[Dict[str, Any]], columns: List[str]) -> None:
    """
    Print rows as a simple fixed-width table with headers.
    Only the specified columns are shown, in that order.
    """
    if not rows:
        print("  (no records found)")
        return

    # Compute column widths (header vs. data)
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    header = "  ".join(col.upper().ljust(widths[col]) for col in columns)
    separator = "  ".join("-" * widths[col] for col in columns)
    print(header)
    print(separator)
    for row in rows:
        line = "  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        print(line)


def print_key_value(data: Dict[str, Any]) -> None:
    """Print a single dict as aligned key: value pairs."""
    if not data:
        print("  (no data)")
        return
    max_key = max(len(k) for k in data)
    for k, v in data.items():
        print(f"  {k.ljust(max_key)} : {v}")


def exit_error(message: str, code: int = 1) -> None:
    """Print a clean error and exit with the given code."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)
