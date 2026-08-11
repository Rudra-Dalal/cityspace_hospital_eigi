"""CRUD operations for handbook vector chunks in MongoDB."""

from typing import Any, Dict, List
from app.core.database import get_database


async def save_handbook_chunk(chunk: Dict[str, Any]) -> None:
    """Save or update a handbook chunk idempotently using document, version, and chunk_index."""
    db = get_database()
    filter_spec = {
        "document": chunk["document"],
        "version": chunk["version"],
        "chunk_index": chunk["chunk_index"],
    }
    await db.handbook_chunks.replace_one(filter_spec, chunk, upsert=True)


async def get_all_handbook_chunks() -> List[Dict[str, Any]]:
    """Retrieve all stored handbook chunks."""
    db = get_database()
    cursor = db.handbook_chunks.find({})
    return await cursor.to_list(length=None)


async def delete_handbook_chunks(document: str = "CityCare-Clinic-Patient-Handbook", version: str = "3.2") -> None:
    """Delete handbook chunks for a given document and version to allow clean re-ingestion."""
    db = get_database()
    await db.handbook_chunks.delete_many({"document": document, "version": version})
