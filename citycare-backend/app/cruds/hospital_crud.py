"""Hospital database queries."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.core.database import get_database


async def create_hospital(document: Dict[str, Any]) -> Dict[str, Any]:
    db = get_database()
    result = await db.hospitals.insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def get_hospital_by_id(hospital_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(hospital_id)
    except InvalidId:
        return None
    return await db.hospitals.find_one({"_id": oid})


async def get_all_hospitals(status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_database()
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    cursor = db.hospitals.find(query).sort("name", 1)
    return [doc async for doc in cursor]


async def update_hospital(hospital_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(hospital_id)
    except InvalidId:
        return None
    updates["updated_at"] = datetime.now(timezone.utc)
    return await db.hospitals.find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )


async def count_hospitals() -> int:
    db = get_database()
    return await db.hospitals.count_documents({})
