"""Appointment endpoint tests including concurrency / no double-booking."""

import asyncio

import pytest

from tests.conftest import auth_header, login, signup_patient, today_iso


def booking_body(date: str, slot: str = "10:00"):
    return {
        "date": date,
        "slot": slot,
        "reason": "Persistent fever and body pain",
        "temperature": 99.5,
        "symptoms": ["fever", "bodyache"],
    }


@pytest.mark.asyncio
async def test_free_slots_excludes_booked(client):
    await signup_patient(client, "free@example.com")
    token = (await login(client, "free@example.com", "Patient@123"))["access_token"]
    date = today_iso()

    before = await client.get(f"/appointments/free-slots?date={date}")
    assert before.status_code == 200
    assert "10:00" in before.json()["free_slots"]

    book = await client.post(
        "/appointments",
        json=booking_body(date, "10:00"),
        headers=auth_header(token),
    )
    assert book.status_code == 201

    after = await client.get(f"/appointments/free-slots?date={date}")
    assert "10:00" not in after.json()["free_slots"]


@pytest.mark.asyncio
async def test_book_requires_auth(client):
    res = await client.post("/appointments", json=booking_body(today_iso()))
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_book_rejects_short_reason(client):
    await signup_patient(client, "short@example.com")
    token = (await login(client, "short@example.com", "Patient@123"))["access_token"]
    body = booking_body(today_iso())
    body["reason"] = "fever"
    res = await client.post("/appointments", json=body, headers=auth_header(token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_book_rejects_past_date(client):
    await signup_patient(client, "past@example.com")
    token = (await login(client, "past@example.com", "Patient@123"))["access_token"]
    body = booking_body("2020-01-01")
    res = await client.post("/appointments", json=body, headers=auth_header(token))
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_double_booking_returns_409(client):
    await signup_patient(client, "p1@example.com")
    await signup_patient(client, "p2@example.com")
    t1 = (await login(client, "p1@example.com", "Patient@123"))["access_token"]
    t2 = (await login(client, "p2@example.com", "Patient@123"))["access_token"]
    date = today_iso()
    body = booking_body(date, "11:00")

    first = await client.post("/appointments", json=body, headers=auth_header(t1))
    assert first.status_code == 201

    second = await client.post("/appointments", json=body, headers=auth_header(t2))
    assert second.status_code == 409
    assert "detail" in second.json()


@pytest.mark.asyncio
async def test_concurrent_booking_only_one_succeeds(client):
    """Race-condition proof: many simultaneous inserts → exactly one 201."""
    emails = [f"race{i}@example.com" for i in range(8)]
    tokens = []
    for email in emails:
        await signup_patient(client, email)
        tokens.append((await login(client, email, "Patient@123"))["access_token"])

    date = today_iso()
    body = booking_body(date, "12:00")

    async def attempt(token: str):
        return await client.post(
            "/appointments",
            json=body,
            headers=auth_header(token),
        )

    results = await asyncio.gather(*[attempt(t) for t in tokens])
    successes = [r for r in results if r.status_code == 201]
    conflicts = [r for r in results if r.status_code == 409]

    assert len(successes) == 1, [r.status_code for r in results]
    assert len(conflicts) == len(tokens) - 1


@pytest.mark.asyncio
async def test_my_appointments_isolation(client):
    await signup_patient(client, "iso1@example.com")
    await signup_patient(client, "iso2@example.com")
    t1 = (await login(client, "iso1@example.com", "Patient@123"))["access_token"]
    t2 = (await login(client, "iso2@example.com", "Patient@123"))["access_token"]
    date = today_iso()

    await client.post(
        "/appointments",
        json=booking_body(date, "17:00"),
        headers=auth_header(t1),
    )
    await client.post(
        "/appointments",
        json=booking_body(date, "17:30"),
        headers=auth_header(t2),
    )

    mine1 = (await client.get("/appointments/my", headers=auth_header(t1))).json()
    mine2 = (await client.get("/appointments/my", headers=auth_header(t2))).json()
    assert len(mine1) == 1
    assert len(mine2) == 1
    assert mine1[0]["slot"] == "17:00"
    assert mine2[0]["slot"] == "17:30"


@pytest.mark.asyncio
async def test_cancel_frees_slot(client):
    await signup_patient(client, "cancel@example.com")
    token = (await login(client, "cancel@example.com", "Patient@123"))["access_token"]
    date = today_iso()

    booked = await client.post(
        "/appointments",
        json=booking_body(date, "18:00"),
        headers=auth_header(token),
    )
    assert booked.status_code == 201
    appt_id = booked.json()["id"]

    cancel = await client.patch(
        f"/appointments/{appt_id}/cancel",
        headers=auth_header(token),
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    free = await client.get(f"/appointments/free-slots?date={date}")
    assert "18:00" in free.json()["free_slots"]

    # Slot can be rebooked after cancel
    again = await client.post(
        "/appointments",
        json=booking_body(date, "18:00"),
        headers=auth_header(token),
    )
    assert again.status_code == 201
