"""User database queries."""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_database


async def create_user(document: Dict[str, Any]) -> Dict[str, Any]:
    db = get_database()
    result = await db.users.insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    return await db.users.find_one({"email": email.lower().strip()})


async def get_user_by_mobile(mobile: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    clean = mobile.strip()
    return await db.users.find_one({"mobile": clean})


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return await db.users.find_one({"_id": oid})


async def count_patients() -> int:
    """Count users with customer or legacy patient role."""
    db = get_database()
    return await db.users.count_documents({"role": {"$in": ["customer", "patient"]}})


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


async def list_users(
    role: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List users with optional role and hospital_id filters."""
    db = get_database()
    query: Dict[str, Any] = {}
    if role:
        query["role"] = role
    if hospital_id:
        query["hospital_id"] = hospital_id
    cursor = db.users.find(query).sort("created_at", -1)
    return [u async for u in cursor]


async def update_user(user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Patch a user document and return the updated doc."""
    db = get_database()
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    await db.users.update_one({"_id": oid}, {"$set": updates})
    return await db.users.find_one({"_id": oid})
