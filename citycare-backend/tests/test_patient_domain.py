"""Comprehensive unit and integration tests for Patient Domain, Multi-Hospital, and Authorization."""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.core.database import get_database
from tests.conftest import auth_header, login, signup_patient, today_iso


@pytest.mark.asyncio
async def test_patient_registration_service_and_duplicate_handling(client: AsyncClient):
    """Test public registration through registration service."""
    # 1. Successful signup
    patient = await signup_patient(client, "test_patient_1@example.com")
    assert patient["email"] == "test_patient_1@example.com"
    assert patient["role"] == "customer"
    assert patient["is_active"] is True
    assert "password" not in patient
    assert "password_hash" not in patient

    # 2. Duplicate signup fails with 400
    res_dup = await client.post(
        "/auth/signup",
        json={
            "first_name": "Test",
            "last_name": "Patient",
            "email": "test_patient_1@example.com",
            "mobile": "+919876543210",
            "password": "Password@123",
        },
    )
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]

    # 3. Client cannot forge privileged role (e.g. super_admin) via public signup
    res_role = await client.post(
        "/auth/signup",
        json={
            "first_name": "Hacker",
            "last_name": "User",
            "email": "hacker@example.com",
            "mobile": "+919876543211",
            "password": "Password@123",
            "role": "super_admin",
        },
    )
    assert res_role.status_code == 201
    assert res_role.json()["role"] == "customer"


@pytest.mark.asyncio
async def test_inactive_user_cannot_login_or_access_protected_routes(client: AsyncClient):
    """Test that deactivated users cannot log in or call protected endpoints."""
    await signup_patient(client, "deactivated@example.com")
    token = (await login(client, "deactivated@example.com", "Patient@123"))["access_token"]

    # Verify working initially
    res_me = await client.get("/appointments/my", headers=auth_header(token))
    assert res_me.status_code == 200

    # Deactivate the user directly in DB
    db = get_database()
    await db.users.update_one({"email": "deactivated@example.com"}, {"$set": {"is_active": False}})

    # 1. Login must fail with 401
    res_login = await client.post(
        "/auth/login",
        json={"email": "deactivated@example.com", "password": "Patient@123"},
    )
    assert res_login.status_code == 401
    assert "deactivated" in res_login.json()["detail"].lower()

    # 2. Existing token on protected endpoint must fail with 401
    res_protected = await client.get("/appointments/my", headers=auth_header(token))
    assert res_protected.status_code == 401
    assert "deactivated" in res_protected.json()["detail"].lower()


@pytest.mark.asyncio
async def test_public_patient_discovery_hospitals_and_doctors(client: AsyncClient):
    """Test public discovery endpoints for hospitals and doctors with filtering."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]

    # Create an active hospital
    res_h1 = await client.post(
        "/admin/hospitals",
        json={
            "name": "Apollo City Hospital",
            "address": "123 Medical Enclave",
            "city": "Mumbai",
            "state": "Maharashtra",
            "contact_phone": "+919123456780",
            "contact_email": "contact@apollo-city.com",
            "facilities": ["Emergency", "ICU", "Cardiology Lab"],
            "services": ["Cardiology", "Diagnostics"],
            "working_hours": "08:00 - 22:00",
            "status": "active",
        },
        headers=auth_header(admin_token),
    )
    assert res_h1.status_code == 201
    h1_id = res_h1.json()["id"]

    # Create an inactive hospital
    res_h2 = await client.post(
        "/admin/hospitals",
        json={
            "name": "Closed Hospital",
            "address": "456 Old Rd",
            "city": "Mumbai",
            "state": "Maharashtra",
            "contact_phone": "+919123456781",
            "contact_email": "closed@hospital.com",
            "facilities": ["None"],
            "services": ["None"],
            "working_hours": "Closed",
            "status": "inactive",
        },
        headers=auth_header(admin_token),
    )
    assert res_h2.status_code == 201
    h2_id = res_h2.json()["id"]

    # Create doctor at active hospital
    res_d1 = await client.post(
        "/admin/users/doctor",
        json={
            "first_name": "Rajesh",
            "last_name": "Sharma",
            "email": "dr.sharma@apollo.com",
            "mobile": "+919876500001",
            "password": "Doctor@123",
            "hospital_id": h1_id,
            "qualification": "MBBS, MD - Cardiology",
            "specialization": "Cardiologist",
        },
        headers=auth_header(admin_token),
    )
    assert res_d1.status_code == 201
    d1_id = res_d1.json()["id"]

    # 1. List active hospitals (public)
    res_hosp_list = await client.get("/patient/hospitals")
    assert res_hosp_list.status_code == 200
    hosp_ids = [h["id"] for h in res_hosp_list.json()]
    assert h1_id in hosp_ids
    assert h2_id not in hosp_ids  # Inactive hospital excluded

    # 2. Get active hospital details
    res_hosp_detail = await client.get(f"/patient/hospitals/{h1_id}")
    assert res_hosp_detail.status_code == 200
    assert res_hosp_detail.json()["name"] == "Apollo City Hospital"
    assert "ICU" in res_hosp_detail.json()["facilities"]

    # 3. Getting inactive hospital details returns 404
    res_hosp_inactive = await client.get(f"/patient/hospitals/{h2_id}")
    assert res_hosp_inactive.status_code == 404

    # 4. List active doctors
    res_doc_list = await client.get("/patient/doctors")
    assert res_doc_list.status_code == 200
    doc_ids = [d["id"] for d in res_doc_list.json()]
    assert d1_id in doc_ids

    # 5. Filter doctors by specialization
    res_cardio = await client.get("/patient/doctors?specialization=Cardiologist")
    assert res_cardio.status_code == 200
    assert any(d["id"] == d1_id for d in res_cardio.json())

    # 6. Filter doctors by non-matching specialization
    res_neuro = await client.get("/patient/doctors?specialization=Neurologist")
    assert res_neuro.status_code == 200
    assert not any(d["id"] == d1_id for d in res_neuro.json())

    # 7. Get doctor public profile
    res_doc_detail = await client.get(f"/patient/doctors/{d1_id}")
    assert res_doc_detail.status_code == 200
    assert res_doc_detail.json()["specialization"] == "Cardiologist"
    assert res_doc_detail.json()["hospital_name"] == "Apollo City Hospital"


@pytest.mark.asyncio
async def test_doctor_availability_and_slots(client: AsyncClient):
    """Test doctor-specific schedule availability and booking subtraction."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]

    # Create hospital and doctor with custom weekday schedule
    res_h = await client.post(
        "/admin/hospitals",
        json={
            "name": "Metro Clinic",
            "address": "789 Metro Ave",
            "city": "Pune",
            "state": "Maharashtra",
            "contact_phone": "+919123456799",
            "contact_email": "metro@clinic.com",
            "status": "active",
        },
        headers=auth_header(admin_token),
    )
    h_id = res_h.json()["id"]

    res_doc = await client.post(
        "/admin/users/doctor",
        json={
            "first_name": "Anita",
            "last_name": "Deshmukh",
            "email": "dr.anita@metro.com",
            "mobile": "+919876500002",
            "password": "Doctor@123",
            "hospital_id": h_id,
            "qualification": "MBBS, DNB",
            "specialization": "Pediatrician",
        },
        headers=auth_header(admin_token),
    )
    doc_id = res_doc.json()["id"]

    # Set doctor available only on Mondays and Wednesdays
    db = get_database()
    from bson import ObjectId
    await db.users.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": {"available_days": ["Monday", "Wednesday"], "valid_slots": ["10:00", "10:30", "11:00"]}},
    )

    # Find the next Monday and next Sunday within 7 days
    today = datetime.now(timezone.utc).date()
    target_monday = None
    target_sunday = None
    for offset in range(1, 8):
        d = today + timedelta(days=offset)
        if d.strftime("%A") == "Monday" and target_monday is None:
            target_monday = d.isoformat()
        if d.strftime("%A") == "Sunday" and target_sunday is None:
            target_sunday = d.isoformat()

    if target_monday:
        res_avail_mon = await client.get(f"/patient/doctors/{doc_id}/availability?date={target_monday}")
        assert res_avail_mon.status_code == 200
        data_mon = res_avail_mon.json()
        assert data_mon["is_available"] is True
        assert data_mon["available_slots"] == ["10:00", "10:30", "11:00"]

    if target_sunday:
        res_avail_sun = await client.get(f"/patient/doctors/{doc_id}/availability?date={target_sunday}")
        assert res_avail_sun.status_code == 200
        data_sun = res_avail_sun.json()
        assert data_sun["is_available"] is False
        assert data_sun["available_slots"] == []


@pytest.mark.asyncio
async def test_appointment_booking_multi_tenant_validation(client: AsyncClient):
    """Test strict hospital and doctor validation during appointment booking."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]
    await signup_patient(client, "booker@example.com")
    patient_token = (await login(client, "booker@example.com", "Patient@123"))["access_token"]

    # Create Hospital A and Hospital B
    res_ha = await client.post(
        "/admin/hospitals",
        json={"name": "Hospital Alpha", "address": "Alpha St", "city": "Delhi", "state": "Delhi", "contact_phone": "+919100000001", "contact_email": "alpha@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    ha_id = res_ha.json()["id"]

    res_hb = await client.post(
        "/admin/hospitals",
        json={"name": "Hospital Beta", "address": "Beta St", "city": "Delhi", "state": "Delhi", "contact_phone": "+919100000002", "contact_email": "beta@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    hb_id = res_hb.json()["id"]

    # Create Inactive Hospital C
    res_hc = await client.post(
        "/admin/hospitals",
        json={"name": "Hospital Inactive", "address": "Inactive St", "city": "Delhi", "state": "Delhi", "contact_phone": "+919100000003", "contact_email": "inactive@hosp.com", "status": "inactive"},
        headers=auth_header(admin_token),
    )
    hc_id = res_hc.json()["id"]

    # Create Doctor assigned to Hospital A
    res_da = await client.post(
        "/admin/users/doctor",
        json={"first_name": "Doctor", "last_name": "Alpha", "email": "dr.alpha@hosp.com", "mobile": "+919876500010", "password": "Doctor@123", "hospital_id": ha_id},
        headers=auth_header(admin_token),
    )
    da_id = res_da.json()["id"]

    date = today_iso()

    # 1. Booking at Inactive Hospital fails with 400
    res_book_inactive_h = await client.post(
        "/appointments",
        json={"hospital_id": hc_id, "doctor_id": da_id, "date": date, "slot": "10:00", "reason": "General checkup consultation"},
        headers=auth_header(patient_token),
    )
    assert res_book_inactive_h.status_code == 400
    assert "hospital is invalid or inactive" in res_book_inactive_h.json()["detail"].lower()

    # 2. Booking with Doctor/Hospital mismatch fails with 400 (Doctor A booked under Hospital B)
    res_book_mismatch = await client.post(
        "/appointments",
        json={"hospital_id": hb_id, "doctor_id": da_id, "date": date, "slot": "10:00", "reason": "General checkup consultation"},
        headers=auth_header(patient_token),
    )
    assert res_book_mismatch.status_code == 400
    assert "does not belong" in res_book_mismatch.json()["detail"].lower()

    # 3. Successful booking with matching active hospital and doctor
    res_book_ok = await client.post(
        "/appointments",
        json={"hospital_id": ha_id, "doctor_id": da_id, "date": date, "slot": "10:00", "reason": "General checkup consultation"},
        headers=auth_header(patient_token),
    )
    assert res_book_ok.status_code == 201
    appt_id = res_book_ok.json()["id"]

    # 4. Duplicate booking for same doctor/slot fails with 409
    res_book_dup = await client.post(
        "/appointments",
        json={"hospital_id": ha_id, "doctor_id": da_id, "date": date, "slot": "10:00", "reason": "Another checkup consultation"},
        headers=auth_header(patient_token),
    )
    assert res_book_dup.status_code == 409


@pytest.mark.asyncio
async def test_prescription_authorization_patient_doctor_manager(client: AsyncClient):
    """Test strict multi-role prescription authorization and manager hospital scoping."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]

    # Create Hospital 1 and Hospital 2
    res_h1 = await client.post(
        "/admin/hospitals",
        json={"name": "Hospital One", "address": "1 Road", "city": "City", "state": "State", "contact_phone": "+919000000001", "contact_email": "h1@test.com"},
        headers=auth_header(admin_token),
    )
    h1_id = res_h1.json()["id"]

    res_h2 = await client.post(
        "/admin/hospitals",
        json={"name": "Hospital Two", "address": "2 Road", "city": "City", "state": "State", "contact_phone": "+919000000002", "contact_email": "h2@test.com"},
        headers=auth_header(admin_token),
    )
    h2_id = res_h2.json()["id"]

    # Manager for Hospital 1
    res_m1 = await client.post(
        "/admin/users/manager",
        json={"first_name": "Manager", "last_name": "One", "email": "m1@hospital1.com", "mobile": "+919876511111", "password": "Manager@123", "hospital_id": h1_id},
        headers=auth_header(admin_token),
    )
    m1_token = (await login(client, "m1@hospital1.com", "Manager@123"))["access_token"]

    # Manager for Hospital 2
    res_m2 = await client.post(
        "/admin/users/manager",
        json={"first_name": "Manager", "last_name": "Two", "email": "m2@hospital2.com", "mobile": "+919876522222", "password": "Manager@123", "hospital_id": h2_id},
        headers=auth_header(admin_token),
    )
    m2_token = (await login(client, "m2@hospital2.com", "Manager@123"))["access_token"]

    # Doctor at Hospital 1
    res_d1 = await client.post(
        "/admin/users/doctor",
        json={"first_name": "Doc", "last_name": "One", "email": "doc1@hospital1.com", "mobile": "+919876533333", "password": "Doctor@123", "hospital_id": h1_id},
        headers=auth_header(admin_token),
    )
    d1_token = (await login(client, "doc1@hospital1.com", "Doctor@123"))["access_token"]
    d1_id = res_d1.json()["id"]

    # Patient A and Patient B
    await signup_patient(client, "patient_a@example.com")
    pt_a_token = (await login(client, "patient_a@example.com", "Patient@123"))["access_token"]

    await signup_patient(client, "patient_b@example.com")
    pt_b_token = (await login(client, "patient_b@example.com", "Patient@123"))["access_token"]

    # Patient A books at Hospital 1 with Doctor 1
    res_appt = await client.post(
        "/appointments",
        json={"hospital_id": h1_id, "doctor_id": d1_id, "date": today_iso(), "slot": "10:30", "reason": "Fever and cold consultation"},
        headers=auth_header(pt_a_token),
    )
    assert res_appt.status_code == 201
    appt_id = res_appt.json()["id"]

    # Doctor 1 accepts appointment
    await client.patch(f"/appointments/{appt_id}/accept", headers=auth_header(d1_token))

    # Doctor 1 creates prescription
    with patch("app.controllers.prescription_controller.upload_prescription_pdf", return_value=("https://example.test/prescription.pdf", "citycare/prescriptions/x")):
        res_presc = await client.post(
            "/prescriptions",
            json={
                "appointment_id": appt_id,
                "diagnosis": "Acute Pharyngitis",
                "medicines": [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "TDS", "duration": "5 days", "instructions": "After meals"}],
                "general_instructions": "Warm water gargle",
            },
            headers=auth_header(d1_token),
        )
    assert res_presc.status_code == 201
    presc_id = res_presc.json()["id"]

    # 1. Patient A can view own prescription
    res_view_a = await client.get(f"/prescriptions/{presc_id}", headers=auth_header(pt_a_token))
    assert res_view_a.status_code == 200
    assert res_view_a.json()["diagnosis"] == "Acute Pharyngitis"

    # 2. Patient B CANNOT view Patient A's prescription (403)
    res_view_b = await client.get(f"/prescriptions/{presc_id}", headers=auth_header(pt_b_token))
    assert res_view_b.status_code == 403

    # 3. Manager 1 (Hospital 1) CAN view prescription via appointment lookup
    res_view_m1 = await client.get(f"/prescriptions/{presc_id}", headers=auth_header(m1_token))
    assert res_view_m1.status_code == 200

    # 4. Manager 2 (Hospital 2) CANNOT view Hospital 1 prescription (403)
    res_view_m2 = await client.get(f"/prescriptions/{presc_id}", headers=auth_header(m2_token))
    assert res_view_m2.status_code == 403

    # 5. Super Admin CAN view any prescription
    res_view_admin = await client.get(f"/prescriptions/{presc_id}", headers=auth_header(admin_token))
    assert res_view_admin.status_code == 200


@pytest.mark.asyncio
async def test_manager_cannot_change_hospital_status(client: AsyncClient):
    """Test that hospital manager cannot change hospital status."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]

    res_h = await client.post(
        "/admin/hospitals",
        json={"name": "Manager Scope Hospital", "address": "Street", "city": "City", "state": "State", "contact_phone": "+919000000009", "contact_email": "mscope@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    h_id = res_h.json()["id"]

    res_m = await client.post(
        "/admin/users/manager",
        json={"first_name": "Hospital", "last_name": "Admin", "email": "hmanager@scope.com", "mobile": "+919876544444", "password": "Manager@123", "hospital_id": h_id},
        headers=auth_header(admin_token),
    )
    m_token = (await login(client, "hmanager@scope.com", "Manager@123"))["access_token"]

    # Manager updates operational details
    res_update_op = await client.patch(
        "/manager/hospital",
        json={"address": "Updated Street 101", "working_hours": "07:00 - 21:00"},
        headers=auth_header(m_token),
    )
    assert res_update_op.status_code == 200
    assert res_update_op.json()["address"] == "Updated Street 101"
    assert res_update_op.json()["status"] == "active"

    # Manager attempting to deactivate should not change status
    res_update_status = await client.patch(
        "/manager/hospital",
        json={"status": "inactive"},
        headers=auth_header(m_token),
    )
    # Status remains active
    h_db = await client.get(f"/patient/hospitals/{h_id}")
    assert h_db.status_code == 200
    assert h_db.json()["status"] == "active"
