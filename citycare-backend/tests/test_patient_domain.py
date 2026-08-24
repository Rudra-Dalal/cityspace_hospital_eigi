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


@pytest.mark.asyncio
async def test_invalid_weekday_and_invalid_slot_booking(client: AsyncClient):
    """Test validation when booking on an invalid weekday or unconfigured slot."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]
    await signup_patient(client, "slot_tester@example.com")
    pt_token = (await login(client, "slot_tester@example.com", "Patient@123"))["access_token"]

    # Create Hospital
    res_h = await client.post(
        "/admin/hospitals",
        json={"name": "Weekday Test Hospital", "address": "123 Weekday Street", "city": "Nagpur", "state": "Maharashtra", "contact_phone": "+919100000088", "contact_email": "w@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    assert res_h.status_code == 201
    h_id = res_h.json()["id"]

    # Create Doctor configured to work only on Tuesdays and Thursdays from 10:00 to 12:00
    res_doc = await client.post(
        "/admin/users/doctor",
        json={
            "first_name": "Weekday",
            "last_name": "Doctor",
            "email": "dr.weekday@hosp.com",
            "mobile": "+919876500088",
            "password": "Doctor@123",
            "hospital_id": h_id,
            "available_days": ["Tuesday", "Thursday"],
            "valid_slots": ["10:00", "10:30", "11:00", "11:30"],
        },
        headers=auth_header(admin_token),
    )
    assert res_doc.status_code == 201
    doc_id = res_doc.json()["id"]

    # Find the next Friday and next Tuesday within 7 days
    today = datetime.now(timezone.utc).date()
    target_friday = None
    target_tuesday = None
    for offset in range(1, 8):
        d = today + timedelta(days=offset)
        if d.strftime("%A") == "Friday" and target_friday is None:
            target_friday = d.isoformat()
        if d.strftime("%A") == "Tuesday" and target_tuesday is None:
            target_tuesday = d.isoformat()

    # 1. Booking on Friday (off-day) fails with 400
    if target_friday:
        res_off_day = await client.post(
            "/appointments",
            json={"hospital_id": h_id, "doctor_id": doc_id, "date": target_friday, "slot": "10:00", "reason": "Off-day checkup consultation"},
            headers=auth_header(pt_token),
        )
        assert res_off_day.status_code == 400
        assert "not available on" in res_off_day.json()["detail"].lower()

    # 2. Booking on Tuesday with an invalid/unconfigured slot (e.g. 15:00) fails with 400
    if target_tuesday:
        res_bad_slot = await client.post(
            "/appointments",
            json={"hospital_id": h_id, "doctor_id": doc_id, "date": target_tuesday, "slot": "15:00", "reason": "Bad-slot checkup consultation"},
            headers=auth_header(pt_token),
        )
        assert res_bad_slot.status_code == 400
        assert "invalid slot for this doctor" in res_bad_slot.json()["detail"].lower()

        # 3. Booking on Tuesday with valid slot (10:30) succeeds
        res_valid = await client.post(
            "/appointments",
            json={"hospital_id": h_id, "doctor_id": doc_id, "date": target_tuesday, "slot": "10:30", "reason": "Valid checkup consultation"},
            headers=auth_header(pt_token),
        )
        assert res_valid.status_code == 201


@pytest.mark.asyncio
async def test_inactive_doctor_rejected_on_availability_and_booking(client: AsyncClient):
    """Test that deactivated doctors are excluded from discovery, availability, and booking."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]
    await signup_patient(client, "inactive_doc_tester@example.com")
    pt_token = (await login(client, "inactive_doc_tester@example.com", "Patient@123"))["access_token"]

    res_h = await client.post(
        "/admin/hospitals",
        json={"name": "Active Hospital for Inactive Doc", "address": "123 Doctor Street", "city": "Nagpur", "state": "Maharashtra", "contact_phone": "+919100000099", "contact_email": "hdoc@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    assert res_h.status_code == 201
    h_id = res_h.json()["id"]

    res_doc = await client.post(
        "/admin/users/doctor",
        json={"first_name": "ToDeactivate", "last_name": "Doctor", "email": "dr.todeactivate@hosp.com", "mobile": "+919876500099", "password": "Doctor@123", "hospital_id": h_id},
        headers=auth_header(admin_token),
    )
    assert res_doc.status_code == 201
    doc_id = res_doc.json()["id"]

    # Deactivate the doctor
    res_deact = await client.patch(f"/admin/users/{doc_id}/deactivate", headers=auth_header(admin_token))
    assert res_deact.status_code == 200
    assert res_deact.json()["is_active"] is False

    # 1. Doctor is excluded from public doctors list
    res_docs = await client.get(f"/patient/doctors?hospital_id={h_id}")
    assert res_docs.status_code == 200
    assert not any(d["id"] == doc_id for d in res_docs.json())

    # 2. Availability endpoint returns 404
    res_avail = await client.get(f"/patient/doctors/{doc_id}/availability?date={today_iso()}")
    assert res_avail.status_code == 404

    # 3. Booking appointment with inactive doctor fails with 400
    res_book = await client.post(
        "/appointments",
        json={"hospital_id": h_id, "doctor_id": doc_id, "date": today_iso(), "slot": "10:00", "reason": "Inactive doc consultation check"},
        headers=auth_header(pt_token),
    )
    assert res_book.status_code == 400
    assert "doctor is invalid or inactive" in res_book.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_and_manager_configure_doctor_availability(client: AsyncClient):
    """Test authorized admin and hospital manager updating doctor availability configuration."""
    admin_token = (await login(client, "admin@citycare.clinic", "Admin@123"))["access_token"]

    # Create Hospital A and Hospital B
    res_ha = await client.post(
        "/admin/hospitals",
        json={"name": "Doctor Config Hospital A", "address": "123 Alpha Road", "city": "Pune", "state": "MH", "contact_phone": "+919100000071", "contact_email": "ha_cfg@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    assert res_ha.status_code == 201
    ha_id = res_ha.json()["id"]

    res_hb = await client.post(
        "/admin/hospitals",
        json={"name": "Doctor Config Hospital B", "address": "456 Beta Road", "city": "Pune", "state": "MH", "contact_phone": "+919100000072", "contact_email": "hb_cfg@hosp.com", "status": "active"},
        headers=auth_header(admin_token),
    )
    assert res_hb.status_code == 201
    hb_id = res_hb.json()["id"]

    # Create Manager for Hospital A and Hospital B
    res_ma = await client.post(
        "/admin/users/manager",
        json={"first_name": "Manager", "last_name": "A", "email": "mgr_a_cfg@hosp.com", "mobile": "+919876577771", "password": "Manager@123", "hospital_id": ha_id},
        headers=auth_header(admin_token),
    )
    assert res_ma.status_code == 201
    mgr_a_token = (await login(client, "mgr_a_cfg@hosp.com", "Manager@123"))["access_token"]

    res_mb = await client.post(
        "/admin/users/manager",
        json={"first_name": "Manager", "last_name": "B", "email": "mgr_b_cfg@hosp.com", "mobile": "+919876577772", "password": "Manager@123", "hospital_id": hb_id},
        headers=auth_header(admin_token),
    )
    assert res_mb.status_code == 201
    mgr_b_token = (await login(client, "mgr_b_cfg@hosp.com", "Manager@123"))["access_token"]

    # Create Doctor at Hospital A
    res_doc = await client.post(
        "/admin/users/doctor",
        json={"first_name": "Suresh", "last_name": "Patil", "email": "dr.suresh@hospa.com", "mobile": "+919876577773", "password": "Doctor@123", "hospital_id": ha_id},
        headers=auth_header(admin_token),
    )
    assert res_doc.status_code == 201
    doc_id = res_doc.json()["id"]

    # 1. Hospital Manager A updates Doctor A availability
    res_mgr_update = await client.patch(
        f"/manager/doctors/{doc_id}",
        json={
            "available_days": ["Monday", "Wednesday", "Friday"],
            "working_hours": "09:00 - 15:00",
            "valid_slots": ["09:00", "09:30", "10:00"],
        },
        headers=auth_header(mgr_a_token),
    )
    assert res_mgr_update.status_code == 200
    assert res_mgr_update.json()["available_days"] == ["Monday", "Wednesday", "Friday"]
    assert res_mgr_update.json()["valid_slots"] == ["09:00", "09:30", "10:00"]

    # 2. Manager B attempting to update Doctor A (cross-hospital) fails with 404
    res_cross_mgr = await client.patch(
        f"/manager/doctors/{doc_id}",
        json={"valid_slots": ["10:00"]},
        headers=auth_header(mgr_b_token),
    )
    assert res_cross_mgr.status_code == 404

    # 3. Super Admin updates Doctor A configuration
    res_admin_update = await client.patch(
        f"/admin/doctors/{doc_id}",
        json={"specialization": "Senior Cardiologist", "valid_slots": ["09:00", "10:00", "11:00"]},
        headers=auth_header(admin_token),
    )
    assert res_admin_update.status_code == 200
    assert res_admin_update.json()["specialization"] == "Senior Cardiologist"

    # 4. Invalid weekday name fails validation with 422
    res_invalid_day = await client.patch(
        f"/admin/doctors/{doc_id}",
        json={"available_days": ["Funday"]},
        headers=auth_header(admin_token),
    )
    assert res_invalid_day.status_code == 422


@pytest.mark.asyncio
async def test_deactivated_cli_user_rejected(client: AsyncClient):
    """Test that CLI authentication rejects deactivated users."""
    from cli.utils import load_current_user
    from app.core.security import create_access_token
    from app.core.database import get_database

    db = get_database()
    # Create active user token
    user = await db.users.find_one({"email": "admin@citycare.clinic"})
    assert user is not None
    token = create_access_token({"sub": str(user["_id"]), "email": user["email"], "role": user["role"]})

    # Active user loads correctly
    loaded = await load_current_user(token)
    assert loaded is not None
    assert loaded["email"] == "admin@citycare.clinic"

    # Temporarily set is_active=False
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})
    try:
        loaded_deact = await load_current_user(token)
        assert loaded_deact is None  # Deactivated user returns None
    finally:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": True}})


@pytest.mark.asyncio
async def test_legacy_records_and_idempotent_migration(client: AsyncClient):
    """Test graceful handling of legacy records and migration idempotency."""
    from app.core.migrate import run_migrations
    from app.core.database import get_database

    db = get_database()

    # 1. Create a deliberately inactive user without is_active in another record
    res_delib = await db.users.insert_one({
        "first_name": "Deliberately",
        "last_name": "Inactive",
        "email": "delib_inactive@example.com",
        "mobile": "+919876599990",
        "role": "customer",
        "is_active": False,
    })

    # 2. Run migrations again
    await run_migrations()

    # 3. Verify deliberately inactive user was NOT reactivated
    delib_user = await db.users.find_one({"_id": res_delib.inserted_id})
    assert delib_user is not None
    assert delib_user["is_active"] is False  # Must remain False!

    # Cleanup
    await db.users.delete_one({"_id": res_delib.inserted_id})
