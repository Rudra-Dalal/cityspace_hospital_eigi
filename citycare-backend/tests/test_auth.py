"""Auth endpoint tests."""

import pytest

from tests.conftest import auth_header, login, signup_patient


@pytest.mark.asyncio
async def test_signup_creates_patient_even_if_role_doctor_sent(client):
    res = await client.post(
        "/auth/signup",
        json={
            "first_name": "Alice",
            "last_name": "Patel",
            "email": "alice@example.com",
            "mobile": "+919811122233",
            "password": "Patient@123",
            "role": "doctor",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["role"] == "patient"
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_signup_duplicate_email(client):
    await signup_patient(client, "dup@example.com")
    res = await client.post(
        "/auth/signup",
        json={
            "first_name": "Dup",
            "last_name": "User",
            "email": "dup@example.com",
            "mobile": "+919811122234",
            "password": "Patient@123",
        },
    )
    assert res.status_code == 400
    assert "detail" in res.json()


@pytest.mark.asyncio
async def test_login_success_and_token_fields(client):
    await signup_patient(client, "bob@example.com")
    data = await login(client, "bob@example.com", "Patient@123")
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "bob@example.com"
    assert data["user"]["role"] == "patient"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await signup_patient(client, "carol@example.com")
    res = await client.post(
        "/auth/login",
        json={"email": "carol@example.com", "password": "WrongPass1"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password."


@pytest.mark.asyncio
async def test_doctor_seed_login(client):
    data = await login(client, "doctor@citycare.clinic", "Doctor@123")
    assert data["user"]["role"] == "doctor"


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client):
    res = await client.get("/appointments/my", headers=auth_header("not.a.jwt"))
    assert res.status_code == 401
