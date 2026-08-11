"""Reusable embedding helper compatible with Gemini embedding models and local fallback."""

import re
import math
import hashlib
from typing import List
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIMENSION = 768


def _local_embedding(text: str, dimensions: int = EMBEDDING_DIMENSION) -> List[float]:
    """
    Local deterministic embedding vectorizer.
    Produces identical-dimension vectors for query & document when Gemini API is unconfigured/testing.
    """
    vector = [0.0] * dimensions
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return vector
    for token in tokens:
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % dimensions
        vector[idx] += 1.0
    magnitude = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / magnitude for v in vector]


async def get_embedding_async(text: str) -> List[float]:
    """Generate embedding vector asynchronously."""
    settings = get_settings()
    api_key = settings.gemini_api_key
    if api_key and not api_key.startswith("your-"):
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            for model_name in ["gemini-embedding-001", "text-embedding-004"]:
                try:
                    response = await client.aio.models.embed_content(
                        model=model_name,
                        contents=text,
                    )
                    if hasattr(response, "embeddings") and response.embeddings:
                        return response.embeddings[0].values
                    if hasattr(response, "embedding") and response.embedding:
                        return response.embedding.values
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Gemini embedding API unavailable, using local vectorizer: %s", exc)

    return _local_embedding(text)


def get_embedding(text: str) -> List[float]:
    """Generate embedding vector synchronously (for ingestion scripts or CLI)."""
    settings = get_settings()
    api_key = settings.gemini_api_key
    if api_key and not api_key.startswith("your-"):
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            for model_name in ["gemini-embedding-001", "text-embedding-004"]:
                try:
                    response = client.models.embed_content(
                        model=model_name,
                        contents=text,
                    )
                    if hasattr(response, "embeddings") and response.embeddings:
                        return response.embeddings[0].values
                    if hasattr(response, "embedding") and response.embedding:
                        return response.embedding.values
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Gemini embedding API unavailable, using local vectorizer: %s", exc)

    return _local_embedding(text)
