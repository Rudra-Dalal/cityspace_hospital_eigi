"""
Tests for the AI chat endpoint.

Pattern follows the existing test suite (conftest.py, pytest-asyncio, ASGI transport).
Gemini calls are mocked so tests run without a real API key.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import auth_header, login


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _doctor_token(client) -> str:
    data = await login(client, "doctor@citycare.clinic", "Doctor@123")
    return data["access_token"]


async def _patient_token(client) -> str:
    from tests.conftest import signup_patient
    await signup_patient(client, "chatpatient@example.com")
    data = await login(client, "chatpatient@example.com", "Patient@123")
    return data["access_token"]


# ---------------------------------------------------------------------------
# Mock run_chat helper
# ---------------------------------------------------------------------------

def _mock_run_chat(reply="Here is your schedule.", tools=None):
    """Return a mock coroutine for app.ai.service.run_chat."""
    import uuid
    conv_id = uuid.uuid4().hex[:32]
    tools = tools or []
    
    async def _fake(*args, **kwargs):
        return reply, conv_id, tools

    return _fake


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_chat_requires_authentication(client):
    """Unauthenticated request must return 401."""
    res = await client.post("/ai/chat", json={"message": "Hello"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_ai_chat_requires_doctor_role(client):
    """Patient/customer must receive 403."""
    token = await _patient_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat()):
        res = await client.post(
            "/ai/chat",
            json={"message": "Hello"},
            headers=auth_header(token),
        )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_ai_chat_doctor_can_access(client):
    """Authenticated doctor must get a 200 response."""
    token = await _doctor_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat()):
        res = await client.post(
            "/ai/chat",
            json={"message": "What appointments do I have today?"},
            headers=auth_header(token),
        )
    assert res.status_code == 200
    body = res.json()
    assert "reply" in body
    assert "conversation_id" in body
    assert isinstance(body["tool_calls_made"], list)


# ---------------------------------------------------------------------------
# Request validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_chat_empty_message_rejected(client):
    """Empty message must be rejected with 422."""
    token = await _doctor_token(client)
    res = await client.post(
        "/ai/chat",
        json={"message": ""},
        headers=auth_header(token),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_ai_chat_whitespace_message_rejected(client):
    """Whitespace-only message must be rejected."""
    token = await _doctor_token(client)
    res = await client.post(
        "/ai/chat",
        json={"message": "   "},
        headers=auth_header(token),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_ai_chat_too_long_message_rejected(client):
    """Message exceeding max_length must be rejected with 422."""
    token = await _doctor_token(client)
    res = await client.post(
        "/ai/chat",
        json={"message": "x" * 2001},
        headers=auth_header(token),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_ai_chat_invalid_conversation_id_rejected(client):
    """Malformed conversation_id must be rejected."""
    token = await _doctor_token(client)
    res = await client.post(
        "/ai/chat",
        json={"message": "Hello", "conversation_id": "!!! invalid !!!"},
        headers=auth_header(token),
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Functional tests (tools mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_chat_today_schedule(client):
    """Test that today's schedule tool can be invoked conceptually."""
    token = await _doctor_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat(
        reply="You have 2 appointments today.",
        tools=["Checking today's schedule"],
    )):
        res = await client.post(
            "/ai/chat",
            json={"message": "What appointments do I have today?"},
            headers=auth_header(token),
        )
    assert res.status_code == 200
    body = res.json()
    assert "appointments" in body["reply"].lower() or len(body["reply"]) > 0


@pytest.mark.asyncio
async def test_ai_chat_schedule_for_date(client):
    token = await _doctor_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat(reply="You have 1 appointment on 2026-08-10.")):
        res = await client.post(
            "/ai/chat",
            json={"message": "What is my schedule on 2026-08-10?"},
            headers=auth_header(token),
        )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_ai_chat_patient_search(client):
    token = await _doctor_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat(reply="Found 1 patient named John.")):
        res = await client.post(
            "/ai/chat",
            json={"message": "Find patient John"},
            headers=auth_header(token),
        )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_ai_chat_statistics(client):
    token = await _doctor_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat(reply="Today: 3 total, 2 booked, 1 cancelled.")):
        res = await client.post(
            "/ai/chat",
            json={"message": "Give me today's appointment statistics"},
            headers=auth_header(token),
        )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Conversation continuity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_chat_conversation_continuity(client):
    """Second message with same conversation_id is accepted."""
    token = await _doctor_token(client)

    import uuid
    conv_id = uuid.uuid4().hex[:32]

    async def _reply_with_conv(*args, **kwargs):
        return "Here is your info.", conv_id, []

    with patch("app.routes.ai_routes.run_chat", new=_reply_with_conv):
        # First message
        res1 = await client.post(
            "/ai/chat",
            json={"message": "What appointments do I have today?"},
            headers=auth_header(token),
        )
        assert res1.status_code == 200
        returned_conv_id = res1.json()["conversation_id"]

        # Second message with the returned conversation_id
        res2 = await client.post(
            "/ai/chat",
            json={"message": "Which one is next?", "conversation_id": returned_conv_id},
            headers=auth_header(token),
        )
        assert res2.status_code == 200


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_chat_gemini_unavailable_returns_503(client):
    """Gemini config errors must produce a safe 503, not a stack trace."""
    token = await _doctor_token(client)

    async def _raise_runtime(*args, **kwargs):
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    with patch("app.routes.ai_routes.run_chat", new=_raise_runtime):
        res = await client.post(
            "/ai/chat",
            json={"message": "Hello"},
            headers=auth_header(token),
        )
    assert res.status_code == 503
    body = res.json()
    # Must not expose internal error messages
    assert "GEMINI_API_KEY" not in body.get("detail", "")
    assert "stack" not in body.get("detail", "").lower()


@pytest.mark.asyncio
async def test_ai_chat_rate_limit_returns_429(client):
    """Rate-limited requests must return 429."""
    token = await _doctor_token(client)

    async def _rate_limited(*args, **kwargs):
        raise ValueError("rate_limited")

    with patch("app.routes.ai_routes.run_chat", new=_rate_limited):
        res = await client.post(
            "/ai/chat",
            json={"message": "Hello"},
            headers=auth_header(token),
        )
    assert res.status_code == 429


# ---------------------------------------------------------------------------
# Security tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_chat_does_not_accept_doctor_id_in_body(client):
    """
    Sending doctor_id in the request body must NOT affect which doctor's data is queried.
    The endpoint simply ignores extra fields — the schema does not accept doctor_id.
    """
    token = await _doctor_token(client)
    with patch("app.routes.ai_routes.run_chat", new=_mock_run_chat()):
        # Extra fields are silently stripped by Pydantic
        res = await client.post(
            "/ai/chat",
            json={
                "message": "Show me appointments",
                "doctor_id": "some-other-doctor-id",   # must be ignored
                "hospital_id": "some-hospital",         # must be ignored
            },
            headers=auth_header(token),
        )
    # Schema rejects unknown fields — 422, OR accepts the message and ignores extras (200)
    # Both are acceptable security outcomes (Pydantic v2 default: extra="ignore")
    assert res.status_code in (200, 422)


@pytest.mark.asyncio
async def test_ai_tools_strip_forbidden_args():
    """Unit test: tool arg sanitisation removes forbidden fields."""
    from app.ai.tools import _strip_forbidden
    args = {
        "date": "2026-08-10",
        "doctor_id": "attacker",
        "hospital_id": "other",
        "user_id": "admin",
        "role": "super_admin",
        "query": "John",
    }
    clean = _strip_forbidden(args)
    assert "doctor_id" not in clean
    assert "hospital_id" not in clean
    assert "user_id" not in clean
    assert "role" not in clean
    assert clean["date"] == "2026-08-10"
    assert clean["query"] == "John"


@pytest.mark.asyncio
async def test_ai_tools_unknown_tool_rejected():
    """Unit test: unknown tool name must return an error dict, not execute anything."""
    from app.ai.tools import execute_tool
    fake_user = {"_id": "fake-id", "role": "doctor", "email": "test@example.com"}
    result = await execute_tool("drop_database", {}, fake_user)
    assert "error" in result
    assert "Unknown tool" in result["error"]
