"""Shared pytest fixtures — uses a dedicated test database."""

import asyncio
import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Point settings at a test DB before importing the app
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ["MONGODB_DB_NAME"] = "citycare_test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DOCTOR_EMAIL", "doctor@citycare.clinic")
os.environ.setdefault("DOCTOR_PASSWORD", "Doctor@123")
os.environ.setdefault("DOCTOR_FIRST_NAME", "Meera")
os.environ.setdefault("DOCTOR_LAST_NAME", "Kulkarni")

from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo, ensure_indexes, get_database
from app.controllers.auth_controller import seed_doctor_if_missing
from app.main import app

get_settings.cache_clear()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def client():
    await connect_to_mongo()
    await ensure_indexes()
    db = get_database()
    await db.users.delete_many({})
    await db.appointments.delete_many({})
    await seed_doctor_if_missing()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await db.users.delete_many({})
    await db.appointments.delete_many({})
    await close_mongo_connection()


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def signup_patient(client: AsyncClient, email: str, password: str = "Patient@123"):
    payload = {
        "first_name": "Test",
        "last_name": "Patient",
        "email": email,
        "mobile": "+919876543210",
        "password": password,
    }
    res = await client.post("/auth/signup", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


async def login(client: AsyncClient, email: str, password: str):
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
