"""Comprehensive unit and integration test suite for CityCare Telephony VoiceBot."""

import pytest
from httpx import AsyncClient
from app.voice.config import get_websocket_stream_url, get_normalized_base_url
from app.voice.service import run_voice_chat, get_call_session, clear_call_session


@pytest.mark.asyncio
async def test_public_base_url_normalization(monkeypatch):
    """Verify PUBLIC_BASE_URL is normalized correctly into wss:// / ws:// stream URLs."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://abc.ngrok-free.app/")
    assert get_normalized_base_url() == "https://abc.ngrok-free.app"
    assert get_websocket_stream_url() == "wss://abc.ngrok-free.app/voice/ws"

    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    assert get_websocket_stream_url() == "ws://localhost:8000/voice/ws"


@pytest.mark.asyncio
async def test_incoming_voice_webhook_returns_twiml(client: AsyncClient, monkeypatch):
    """Verify POST /voice/incoming returns valid TwiML XML containing Connect/Stream."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://demo.ngrok-free.app")

    response = await client.post("/voice/incoming", data={"CallSid": "CA123456", "From": "+1234567890"})
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "")

    xml_text = response.text
    assert "<Response>" in xml_text
    assert "<Connect>" in xml_text
    assert "<Stream" in xml_text
    assert 'url="wss://demo.ngrok-free.app/voice/ws"' in xml_text
    assert 'name="call_sid"' in xml_text


@pytest.mark.asyncio
async def test_voice_chat_service_answers_general_handbook_question(client: AsyncClient):
    """Verify run_voice_chat retrieves grounded answers from Handbook RAG for callers."""
    from unittest.mock import MagicMock, patch
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Clinic consultation hours are 9 AM to 8 PM Monday to Saturday."
    mock_genai_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_genai_client):
        reply = await run_voice_chat("What are the consultation hours?", call_sid="test_call_1")
    assert isinstance(reply, str)
    assert len(reply) > 10
    # Spoken responses must not contain markdown formatting
    assert "*" not in reply
    assert "#" not in reply

    # Verify per-call multi-turn history was stored
    history = get_call_session("test_call_1")
    assert len(history) == 1
    assert history[0]["user"] == "What are the consultation hours?"
    clear_call_session("test_call_1")


@pytest.mark.asyncio
async def test_voice_chat_service_blocks_unauthenticated_patient_data():
    """Verify phone calls refuse private patient prescription requests without authentication."""
    reply = await run_voice_chat("What medicine was prescribed to me?", call_sid="test_privacy_call")
    assert "privacy" in reply.lower() or "website" in reply.lower()
    clear_call_session("test_privacy_call")


@pytest.mark.asyncio
async def test_voice_websocket_route_exists(client: AsyncClient):
    """Verify /voice/ws and /voice/incoming routes are registered in FastAPI application."""
    from app.main import app

    def _extract_paths(routes):
        paths = []
        for r in routes:
            if hasattr(r, "path") and r.path:
                paths.append(r.path)
            if hasattr(r, "include_context") and hasattr(r.include_context, "included_router"):
                paths.extend(_extract_paths(r.include_context.included_router.routes))
        return paths

    paths = _extract_paths(app.routes)
    assert "/voice/ws" in paths
    assert "/voice/incoming" in paths

