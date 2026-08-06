"""User database queries."""

from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_database
from app.models.user_model import UserRole


async def create_user(document: Dict[str, Any]) -> Dict[str, Any]:
    db = get_database()
    result = await db.users.insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    return await db.users.find_one({"email": email.lower().strip()})


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return await db.users.find_one({"_id": oid})


async def count_patients() -> int:
    db = get_database()
    return await db.users.count_documents({"role": UserRole.PATIENT.value})


async def get_users_by_ids(user_ids: list) -> Dict[str, Dict[str, Any]]:
    """Return a map of string id → user doc for the given ids."""
    db = get_database()
    oids = []
    for uid in user_ids:
        try:
            oids.append(ObjectId(uid))
        except (InvalidId, TypeError):
            continue
    if not oids:
        return {}
    cursor = db.users.find({"_id": {"$in": oids}})
    mapping: Dict[str, Dict[str, Any]] = {}
    async for user in cursor:
        mapping[str(user["_id"])] = user
    return mapping
