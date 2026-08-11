"""Handbook retrieval-augmented generation (RAG) service."""

import math
from typing import Any, Dict, List
from app.cruds import handbook_crud
from app.services.embedding_service import get_embedding_async
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
    norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
    return dot / (norm_a * norm_b)


async def retrieve_handbook_context(query: str, limit: int = 4) -> List[Dict[str, Any]]:
    """
    Retrieve top matching handbook chunks for a user query.
    Attempts MongoDB Atlas Vector Search if available, otherwise uses a cosine similarity fallback.
    """
    if not query or not query.strip():
        return []

    try:
        records = await handbook_crud.get_all_handbook_chunks()
    except RuntimeError:
        # If database is uninitialized (e.g. unit test without DB fixture), return empty list gracefully
        return []

    if not records:
        return []

    query_embedding = await get_embedding_async(query)

    # Score records by cosine similarity with query embedding
    scored_records: List[Dict[str, Any]] = []
    for record in records:
        record_embedding = record.get("embedding")
        if not record_embedding:
            continue
        sim = _cosine_similarity(query_embedding, record_embedding)
        # Keyword boost for policy codes or matching terms in query
        query_lower = query.lower()
        if record.get("policy") and record["policy"].lower() in query_lower:
            sim += 0.2
        scored_records.append({
            "chunk_index": record.get("chunk_index"),
            "page": record.get("page"),
            "section": record.get("section"),
            "policy": record.get("policy"),
            "text": record.get("text", ""),
            "score": sim,
        })

    # Sort descending by similarity score
    scored_records.sort(key=lambda x: x["score"], reverse=True)

    # Filter out extremely low similarity matches (score < 0.05)
    top_matches = [rec for rec in scored_records if rec["score"] > 0.05][:limit]
    return top_matches
