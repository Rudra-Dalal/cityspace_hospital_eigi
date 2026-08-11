"""Comprehensive tests for Handbook RAG system and Patient AI Chat integration."""

import os
import pytest
from httpx import AsyncClient
from app.services.pdf_extractor import load_pdf_pages, extract_handbook_chunks
from app.services.embedding_service import get_embedding, get_embedding_async
from app.services.handbook_rag import retrieve_handbook_context
from app.cruds.handbook_crud import save_handbook_chunk, get_all_handbook_chunks, delete_handbook_chunks
from tests.conftest import signup_patient, login


PDF_PATH = os.path.join("data", "CityCare-Clinic-Patient-Handbook.pdf")


@pytest.mark.asyncio
async def test_pdf_loading_and_page_count():
    """Verify PDF loads successfully and has 12 pages."""
    pages = load_pdf_pages(PDF_PATH)
    assert len(pages) == 12
    assert pages[0]["page"] == 1
    assert "CityCare Clinic" in pages[0]["text"]


@pytest.mark.asyncio
async def test_text_extraction_and_chunking():
    """Verify text extraction, chunking, and metadata preservation."""
    chunks = extract_handbook_chunks(PDF_PATH)
    assert len(chunks) > 0

    # Verify chunk metadata fields
    first = chunks[0]
    assert first["document"] == "CityCare-Clinic-Patient-Handbook"
    assert first["version"] == "3.2"
    assert isinstance(first["page"], int)
    assert first["page"] >= 1
    assert "section" in first
    assert "text" in first
    assert "chunk_index" in first

    # Check policy metadata preservation on chunks with policy codes
    policy_chunks = [c for c in chunks if c.get("policy")]
    assert len(policy_chunks) > 0
    policies_found = {c["policy"] for c in policy_chunks}
    assert "POL-HRS-00" in policies_found or "POL-APT-01" in policies_found or "POL-FEE-04" in policies_found


@pytest.mark.asyncio
async def test_embedding_generation():
    """Verify embeddings are generated with consistent dimensions."""
    emb_sync = get_embedding("Consultation hours")
    emb_async = await get_embedding_async("Consultation hours")
    assert isinstance(emb_sync, list)
    assert len(emb_sync) > 0
    assert len(emb_sync) == len(emb_async)


@pytest.mark.asyncio
async def test_idempotent_ingestion(client: AsyncClient):
    """Verify storing handbook chunks is idempotent."""
    await delete_handbook_chunks()
    chunk = {
        "document": "CityCare-Clinic-Patient-Handbook",
        "version": "3.2",
        "page": 3,
        "section": "3. Consultation hours (Policy POL-HRS-00)",
        "policy": "POL-HRS-00",
        "chunk_index": 0,
        "text": "Monday 10:00 - 13:00, 17:00 - 20:00",
        "embedding": get_embedding("Monday 10:00 - 13:00"),
    }

    # Save twice
    await save_handbook_chunk(chunk)
    await save_handbook_chunk(chunk)

    all_chunks = await get_all_handbook_chunks()
    matching = [c for c in all_chunks if c["chunk_index"] == 0]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_handbook_retrieval_and_no_results(client: AsyncClient):
    """Verify handbook retrieval for queries and handling no-result cases."""
    # Ensure test chunk exists
    await delete_handbook_chunks()
    chunk = {
        "document": "CityCare-Clinic-Patient-Handbook",
        "version": "3.2",
        "page": 5,
        "section": "5. Fees and payment (Policy POL-FEE-04)",
        "policy": "POL-FEE-04",
        "chunk_index": 1,
        "text": "First consultation fee is 600 INR. Follow-up consultation within 15 days is 300 INR.",
        "embedding": get_embedding("First consultation fee 600 INR follow-up 300 INR"),
    }
    await save_handbook_chunk(chunk)

    # Retrieval matching
    results = await retrieve_handbook_context("What is the first consultation fee?", limit=4)
    assert len(results) > 0
    assert results[0]["page"] == 5
    assert results[0]["policy"] == "POL-FEE-04"

    # Empty query handling
    empty_res = await retrieve_handbook_context("")
    assert empty_res == []


@pytest.mark.asyncio
async def test_patient_ai_chat_with_handbook(client: AsyncClient):
    """Verify POST /patient-ai/chat integrates handbook RAG for general clinic questions."""
    await delete_handbook_chunks()
    chunks = extract_handbook_chunks(PDF_PATH)
    for c in chunks[:10]:
        c["embedding"] = get_embedding(c["text"])
        await save_handbook_chunk(c)

    await signup_patient(client, "patient_handbook@example.com", "Patient@123")
    login_data = await login(client, "patient_handbook@example.com", "Patient@123")
    token = login_data["access_token"]

    questions = [
        "What are the consultation hours?",
        "How much is a first consultation?",
        "How much is a follow-up consultation within 15 days?",
        "Can I cancel an appointment one hour before?",
        "How many days in advance can I book?",
        "Does the clinic have an X-ray machine?",
        "Do you treat children under 13?",
        "What are the teleconsultation cancellation rules?",
        "Does CityCare provide cashless insurance?",
        "What are the emergency instructions?",
        "How long are medical records retained?",
    ]

    headers = {"Authorization": f"Bearer {token}"}
    for q in questions[:3]:
        res = await client.post("/patient-ai/chat", json={"message": q}, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "reply" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
