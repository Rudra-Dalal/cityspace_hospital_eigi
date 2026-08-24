# CityCare Multi-Hospital Clinic Platform — Backend

Multi-hospital healthcare management and appointment booking API built with **FastAPI**, **Motor (Async MongoDB)**, **JWT Authentication**, and **Pytest**.

## Key Features

- **Multi-Tenant Architecture**: Support for multiple hospitals, hospital managers, specialist doctors, and patients.
- **Public Discovery & Doctor Availability**: Public endpoints for listing active hospitals, active doctors, specialization filtering, and doctor-specific weekly schedules with booked slot subtraction.
- **Reusable Patient Registration Service**: Centralized `register_patient` service with mobile normalization (+91), password policy enforcement, duplicate prevention, and customer role isolation.
- **Strict Authorization Hierarchy**:
  - **Super Admin**: Full hospital lifecycle (create, update, activate/deactivate) and user management.
  - **Hospital Manager**: Update branch operational information (address, hours, contact, services); cannot deactivate hospital; access appointments and prescriptions scoped to their hospital via `appointment.hospital_id`.
  - **Doctor**: Manage own schedules, accept appointments, issue official prescriptions with PDF generation.
  - **Customer (Patient)**: Discover active hospitals/specialists, book explicit visits, and view own records with zero cross-tenant leakage.
  - **Deactivated Accounts**: Blocked from login and protected endpoints (401 Unauthorized).
- **Concurrency & Double-Booking Prevention**: Partial unique index on `(hospital_id, doctor_id, date, slot)` for `status="booked"` ensuring atomic slot reservations under race conditions.
- **AI-Powered Services**: Handbook RAG for clinic policies, patient-isolated prescription RAG, and Twilio real-time VoiceBot.

---

## Setup & Running

### Prerequisites

- Python 3.11+
- MongoDB 6+ running locally or reachable via URI

```bash
cd citycare-backend
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

### Run Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Base: http://localhost:8000
- Swagger UI Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## Seeded Accounts

Seeded automatically on startup if missing:

| Role | Email | Default Password |
|------|-------|------------------|
| Super Admin | `admin@citycare.clinic` | `Admin@123` |
| Doctor | `doctor@citycare.clinic` | `Doctor@123` |

---

## API Endpoints

### 1. Authentication & Patient Registration
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | Public | Register patient via reusable registration service (enforces role=`customer`) |
| POST | `/auth/login` | Public | Authenticate user, checks `is_active`, returns JWT token |

### 2. Public Patient Discovery & Doctor Availability
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/patient/hospitals` | Public | List all active hospitals with facilities and contact info |
| GET | `/patient/hospitals/{id}` | Public | Get details of an active hospital |
| GET | `/patient/doctors` | Public | List active doctors (filter by `hospital_id` or `specialization`) |
| GET | `/patient/doctors/{id}` | Public | Get public profile of an active doctor |
| GET | `/patient/doctors/{id}/availability?date=YYYY-MM-DD` | Public | Compute doctor's weekday availability and remaining free slots |

### 3. Appointments
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/appointments` | Patient JWT | Book an appointment with explicit `hospital_id` & `doctor_id` |
| GET | `/appointments/my` | Patient JWT | List authenticated patient's appointments |
| PATCH | `/appointments/{id}/cancel` | Owner / Doctor | Cancel appointment and atomically free the slot |
| PATCH | `/appointments/{id}/accept` | Doctor JWT | Accept assigned appointment |

### 4. Prescriptions
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/prescriptions` | Doctor JWT | Create prescription with PDF upload for accepted appointment |
| GET | `/prescriptions/{id}` | Authorized JWT | Get prescription (Patient owner, Doctor issuer, Manager of hospital, Admin) |
| GET | `/prescriptions/my` | Patient JWT | List patient's own prescriptions |

### 5. Hospital Manager
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/manager/hospital` | Manager JWT | Get manager's assigned hospital |
| PATCH | `/manager/hospital` | Manager JWT | Update operational fields (name, address, hours, facilities) |
| GET | `/manager/doctors` | Manager JWT | List doctors assigned to manager's hospital |
| GET | `/manager/appointments` | Manager JWT | List appointments booked at manager's hospital |

### 6. Super Admin
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/hospitals` | Admin JWT | List all hospitals (active & inactive) |
| POST | `/admin/hospitals` | Admin JWT | Create a new hospital |
| PATCH | `/admin/hospitals/{id}` | Admin JWT | Update any hospital field including `status` |
| GET | `/admin/users` | Admin JWT | List users across roles and hospitals |
| POST | `/admin/users/manager` | Admin JWT | Create a hospital manager |
| POST | `/admin/users/doctor` | Admin JWT | Create a doctor with schedule configuration |
| PATCH | `/admin/users/{id}/deactivate` | Admin JWT | Deactivate a user |

---

## Doctor Availability Strategy

The platform supports doctor-specific availability schedules:
- Each doctor has `available_days` (e.g. `["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]`), `working_hours`, and `valid_slots`.
- When requesting `/patient/doctors/{id}/availability?date=YYYY-MM-DD`:
  1. The target date's weekday name is calculated.
  2. If the day is not in `available_days`, `is_available: false` and `available_slots: []` are returned.
  3. Otherwise, booked appointments for that doctor on that date are queried and subtracted from the doctor's `valid_slots`.

---

## Concurrency & Integrity

1. **Multi-Tenant Booking Validation**:
   - Ensures `hospital_id` exists and has `status="active"`.
   - Ensures `doctor_id` exists, has `is_active=True`, and is assigned to the selected `hospital_id`.
   - Validates date is within the rolling booking window and slot matches doctor's schedule.
2. **Atomic Partial Unique Index**:
   - `uniq_booked_hospital_doctor_date_slot` on `(hospital_id, doctor_id, date, slot)` WHERE `status="booked"`.
   - Competing concurrent requests are rejected with HTTP 409 Conflict.

---

## Testing

Run the comprehensive async pytest suite:

```bash
pytest -v
```

All 98 tests pass across authentication, CLI, appointments, doctor availability, prescriptions, handbook RAG, and patient domain authorization.
