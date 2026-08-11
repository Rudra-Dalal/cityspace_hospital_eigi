"""Ingestion script for CityCare Clinic Patient Handbook.

Loads PDF, extracts text, generates semantic chunks with metadata,
computes embeddings, and stores them idempotently in MongoDB.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to sys.path if running as standalone script
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import connect_to_mongo, close_mongo_connection, ensure_indexes
from app.services.pdf_extractor import extract_handbook_chunks
from app.services.embedding_service import get_embedding
from app.cruds.handbook_crud import save_handbook_chunk, delete_handbook_chunks
from app.utils.logger import get_logger

logger = get_logger(__name__)


def locate_pdf() -> Path:
    """Locate the handbook PDF whether script is executed from backend dir or workspace root."""
    possible_paths = [
        backend_dir / "data" / "CityCare-Clinic-Patient-Handbook.pdf",
        backend_dir.parent / "data" / "CityCare-Clinic-Patient-Handbook.pdf",
        Path("data/CityCare-Clinic-Patient-Handbook.pdf"),
    ]
    for path in possible_paths:
        if path.exists():
            return path
    raise FileNotFoundError("Could not locate CityCare-Clinic-Patient-Handbook.pdf in data/ directory.")


async def ingest_handbook() -> int:
    pdf_path = locate_pdf()
    print(f"Loading handbook PDF from: {pdf_path}")

    # Extract semantic chunks from PDF
    chunks = extract_handbook_chunks(str(pdf_path))
    print(f"Extracted {len(chunks)} chunks across pages.")

    # Connect to MongoDB
    await connect_to_mongo()
    await ensure_indexes()

    # Clear existing chunks for clean idempotent update
    await delete_handbook_chunks(document="CityCare-Clinic-Patient-Handbook", version="3.2")

    # Generate embeddings and save to MongoDB
    for chunk in chunks:
        chunk["embedding"] = get_embedding(chunk["text"])
        await save_handbook_chunk(chunk)

    print(f"Successfully ingested {len(chunks)} handbook chunks into MongoDB collection 'handbook_chunks'.")
    await close_mongo_connection()
    return len(chunks)


def main():
    try:
        count = asyncio.run(ingest_handbook())
        print(f"Handbook ingestion complete! Total chunks stored: {count}")
    except Exception as exc:
        print(f"Error during handbook ingestion: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
