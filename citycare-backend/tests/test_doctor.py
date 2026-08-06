"""Doctor endpoint tests — 401 vs 403 and schedule/stats."""

import pytest

from tests.conftest import auth_header, login, signup_patient, today_iso


@pytest.mark.asyncio
async def test_doctor_info_is_public(client):
    res = await client.get("/doctor/info")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Dr. Meera Kulkarni"
    assert body["clinic_name"] == "CityCare Clinic"
    assert len(body["valid_slots"]) == 12


@pytest.mark.asyncio
async def test_patient_token_on_doctor_stats_returns_403(client):
    await signup_patient(client, "noperm@example.com")
    token = (await login(client, "noperm@example.com", "Patient@123"))["access_token"]
    res = await client.get("/doctor/stats", headers=auth_header(token))
    assert res.status_code == 403
    assert "detail" in res.json()


@pytest.mark.asyncio
async def test_missing_token_on_doctor_stats_returns_401(client):
    res = await client.get("/doctor/stats")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_doctor_stats_and_schedule(client):
    await signup_patient(client, "vis@example.com")
    ptoken = (await login(client, "vis@example.com", "Patient@123"))["access_token"]
    date = today_iso()

    await client.post(
        "/appointments",
        json={
            "date": date,
            "slot": "19:00",
            "reason": "Routine checkup for headache",
            "symptoms": ["headache"],
        },
        headers=auth_header(ptoken),
    )

    dtoken = (await login(client, "doctor@citycare.clinic", "Doctor@123"))["access_token"]

    stats = await client.get("/doctor/stats", headers=auth_header(dtoken))
    assert stats.status_code == 200
    body = stats.json()
    assert body["total_patients"] >= 1
    assert body["today_visits"] >= 1
    assert body["upcoming_visits"] >= 1

    schedule = await client.get(
        f"/doctor/schedule?date={date}",
        headers=auth_header(dtoken),
    )
    assert schedule.status_code == 200
    rows = schedule.json()
    assert any(r["slot"] == "19:00" for r in rows)
    assert any("vis" in r["patient_name"].lower() or "Test" in r["patient_name"] for r in rows)
    row = next(r for r in rows if r["slot"] == "19:00")
    assert row["reason"]
    assert "headache" in row["symptoms"]
