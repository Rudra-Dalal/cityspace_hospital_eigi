# CityCare Multi-Hospital Clinic Platform — Backend

Multi-hospital healthcare management and appointment booking API built with **FastAPI**, **Motor (Async MongoDB)**, **JWT Authentication**, and **Pytest**.

---

## Key Features

- **Multi-Tenant Architecture**: Multi-hospital data isolation, hospital branch managers, specialist doctors, and patient records.
- **Public Discovery & Doctor Availability**: Public endpoints for listing active hospitals, active doctors, specialization filtering, and doctor-specific weekly schedules with booked slot subtraction.
- **Reusable Patient Registration Service**: Standardized `register_patient` service with E.164 phone formatting (+91), password security, duplicate prevention, and strict `customer` role enforcement.
- **Strict Multi-Role Scoped Authorization**:
  - **Super Admin**: Full hospital branch lifecycle (create, update, activate/deactivate), doctor configuration, and global user management.
  - **Hospital Manager**: Update branch operational info (address, hours, contact, services); cannot deactivate hospital; access appointments and prescriptions scoped strictly to their hospital (`prescription → appointment → hospital_id`).
  - **Doctor**: Manage own availability, accept appointments, issue official prescriptions with PDF generation.
  - **Customer (Patient)**: Discover active branches/specialists, book explicit visits, and access own prescriptions with zero data leakage.
  - **Deactivated Accounts**: Blocked from login, JWT-protected API routes, and CLI access with `401 Unauthorized`.
- **Atomic Concurrency & Anti-Double-Booking**: MongoDB partial unique index on `(hospital_id, doctor_id, date, slot)` for `status="booked"`.
- **AI Clinical Services**: Handbook RAG for clinic policies, patient-isolated prescription RAG, and Twilio real-time VoiceBot.

---

## Setup & Running

### Prerequisites

- Python 3.11+
- MongoDB 6+ running locally or accessible via URI

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

- **API Base**: http://localhost:8000
- **Interactive Swagger Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## Seeded Accounts

Seeded automatically on startup if missing:

| Role | Email | Default Password |
|---|---|---|
| **Super Admin** | `admin@citycare.clinic` | `Admin@123` |
| **Doctor** | `doctor@citycare.clinic` | `Doctor@123` |

---

## Complete API Endpoint Reference

### 1. Authentication & Registration
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | Public | Register patient via reusable registration service (enforces role=`customer`) |
| POST | `/auth/login` | Public | Authenticate user, checks `is_active`, returns JWT token |

### 2. Public Patient Discovery & Doctor Availability
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/patient/hospitals` | Public | List all active hospitals with facilities and contact info |
| GET | `/patient/hospitals/{id}` | Public | Get details of an active hospital |
| GET | `/patient/doctors` | Public | List active doctors (query filters: `hospital_id`, `specialization`) |
| GET | `/patient/doctors/{id}` | Public | Get public profile of an active doctor |
| GET | `/patient/doctors/{id}/availability?date=YYYY-MM-DD` | Public | Compute doctor's weekday availability and remaining free slots |

### 3. Appointments & Scheduling
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/appointments` | Patient JWT | Book an appointment with explicit `hospital_id` & `doctor_id` |
| GET | `/appointments/my` | Patient JWT | List authenticated patient's appointments |
| PATCH | `/appointments/{id}/cancel` | Owner / Doctor | Cancel appointment and atomically free the slot |
| PATCH | `/appointments/{id}/accept` | Doctor JWT | Accept assigned appointment |

### 4. Prescriptions Workflow
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/prescriptions` | Doctor JWT | Create prescription with PDF upload for accepted appointment |
| GET | `/prescriptions/{id}` | Authorized JWT | Get prescription (Patient owner, Doctor issuer, Manager of hospital, Admin) |
| GET | `/prescriptions/my` | Patient JWT | List patient's own prescriptions |
| GET | `/prescriptions/patient/{patient_id}` | Doctor JWT | View patient prescription history |
| POST | `/prescriptions/doctor/accept` | Doctor JWT | Accept appointment directly from prescriptions workflow |

### 5. Hospital Manager (Scoped to Manager's Assigned Hospital)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/manager/hospital` | Manager JWT | Get manager's assigned hospital |
| PATCH | `/manager/hospital` | Manager JWT | Update operational fields (name, address, hours, facilities) |
| GET | `/manager/doctors` | Manager JWT | List doctors assigned to manager's hospital |
| PATCH | `/manager/doctors/{doctor_id}` | Manager JWT | Update doctor availability & schedule for hospital doctors |
| GET | `/manager/appointments` | Manager JWT | List appointments booked at manager's hospital |

### 6. Super Admin (Global Management)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/hospitals` | Admin JWT | List all hospitals (active & inactive) |
| POST | `/admin/hospitals` | Admin JWT | Create a new hospital branch |
| PATCH | `/admin/hospitals/{id}` | Admin JWT | Update any hospital field including lifecycle `status` |
| GET | `/admin/users` | Admin JWT | List users across all roles and hospitals |
| POST | `/admin/users/manager` | Admin JWT | Create a hospital manager assigned to a hospital |
| POST | `/admin/users/doctor` | Admin JWT | Create a doctor with specialization and schedule configuration |
| POST | `/admin/users/patient` | Admin JWT | Create a patient account |
| PATCH | `/admin/doctors/{doctor_id}` | Admin JWT | Update doctor specialization, qualifications, and schedules |
| PATCH | `/admin/users/{id}/deactivate` | Admin JWT | Deactivate a user |

### 7. Doctor Portal
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/doctor/stats` | Doctor JWT | Get consultation statistics and today's schedule count |
| GET | `/doctor/schedule` | Doctor JWT | Get doctor schedule for today or a specific date |
| GET | `/doctor/info` | Public | Get legacy single-clinic constant info (backward compat) |

### 8. AI Clinical Assistant & RAG
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/ai/chat/query` | Authenticated | Query AI assistant with context-aware RAG |
| POST | `/ai/chat/stream` | Authenticated | Stream AI assistant response |
| GET | `/ai/chat/conversations` | Authenticated | List previous AI chat conversations |
| GET | `/ai/chat/conversations/{id}` | Authenticated | Retrieve conversation history |
| DELETE | `/ai/chat/conversations/{id}` | Authenticated | Delete a conversation |

### 9. Real-Time Telephony VoiceBot
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/voice/incoming` | Public (Twilio) | TwiML webhook to initiate voice streaming call |
| POST | `/voice/chat` | Public | Process incoming transcribed voice query |
| POST | `/voice/status` | Public (Twilio) | Handle Twilio call status events |
| GET | `/voice/summary` | Authenticated | Retrieve call transcripts and summary |
| GET | `/voice/session-status` | Authenticated | Check status of active voice session |
| WebSocket | `/voice/stream` | Public (Twilio) | Bidirectional media audio stream |

---

## Multi-Hospital Setup Workflow

To set up a production multi-hospital environment:

1. **Start Backend & Seed Admin**:
   Start the backend to trigger automatic migrations and seed the Super Admin (`admin@citycare.clinic`).
2. **Create Hospital Branches**:
   Super Admin logs in (`POST /auth/login`) and creates hospital branches via `POST /admin/hospitals`.
3. **Provision Branch Managers**:
   Super Admin creates a manager for each branch via `POST /admin/users/manager` passing `hospital_id`.
4. **Provision Specialist Doctors**:
   Super Admin creates doctors via `POST /admin/users/doctor` with `hospital_id`, `specialization`, `available_days`, and `valid_slots`.
5. **Tune Doctor Schedules**:
   Either Super Admin (`PATCH /admin/doctors/{id}`) or the Branch Manager (`PATCH /manager/doctors/{id}`) can modify working days and slots.

---

## Doctor Specialization & Availability Configuration

### Schema & Schedule Structure
Doctors have dedicated availability properties in MongoDB:
- `specialization` (e.g. `"Cardiology"`, `"Neurology"`, `"Orthopedics"`, `"General Medicine"`)
- `qualification` (e.g. `"MD, DM (Cardiology)"`)
- `available_days` (Array of valid weekdays: `["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]`)
- `working_hours` (Human-readable range: `"09:00 - 17:00"`)
- `valid_slots` (Array of selectable slot strings: `["09:00", "09:30", "10:00", "10:30", "11:00", ...]`)
- `slot_duration_minutes` (Default: `30`)

### Weekday Availability Logic
When a patient or client queries `GET /patient/doctors/{id}/availability?date=YYYY-MM-DD`:
1. The target date is parsed and converted to its weekday name (`Monday` through `Sunday`).
2. If the day is **not** in `available_days`, the API responds with:
   ```json
   {
     "doctor_id": "<ID>",
     "doctor_name": "Dr. Ananya Sharma",
     "date": "2026-08-30",
     "weekday": "Sunday",
     "is_available": false,
     "available_slots": [],
     "booked_slots": []
   }
   ```
3. If the day **is** in `available_days`, existing active appointments (`status="booked"`) for that doctor and date are subtracted from `valid_slots`, returning all open slots.

---

## Migration & Database Notes

- **Automated Execution**: Migrations execute on startup via `app.core.migrate.run_migrations()`.
- **Idempotency**: All updates use conditional `$exists: False` queries, ensuring zero data loss and zero overwrites of existing customizations.
- **Safety**:
  - Deliberately deactivated users (`is_active: False`) are **never** reactivated.
  - Deactivated hospital branches (`status: "inactive"`) are **never** reactivated.
- **Indexes Created**:
  - `users.email` (unique)
  - `users: [("hospital_id", 1), ("role", 1), ("is_active", 1)]`
  - `users: [("role", 1), ("specialization", 1), ("is_active", 1)]`
  - `hospitals: [("name", 1), ("city", 1)]` (unique)
  - `hospitals.status`
  - `appointments: (hospital_id, doctor_id, date, slot)` partial unique index WHERE `status="booked"`
  - `prescriptions.appointment_id` (unique)

---

---

## Telegram Patient Assistant Gateway

The Telegram Patient Assistant (`telegram_gateway/`) allows patients to discover hospitals, find specialist doctors, check real-time availability, book appointments, access prescriptions with secure PDF delivery, and ask clinic/health questions.

### Gateway Architecture
- **Process Separation**: Polling runs in a separate process (`python -m telegram_gateway.poller`), while production uses FastAPI Webhook (`POST /telegram/webhook`).
- **Persistent Sessions**: Backed by MongoDB (`telegram_sessions`) with deterministic session keys (`tg:private:<chat_id>:0`) and TTL auto-expiration.
- **Identity & Linking**: Immutable numeric Telegram User ID mapped 1-to-1 to Patient ID with salted OTP verification.
- **Password Activation**: Telegram registration creates the patient account and sends a secure one-time activation link to set web credentials on the portal; no passwords in Telegram.
- **Distributed Rate Limiting**: MongoDB atomic counter (`telegram_rate_limits`) with TTL windows safe across multiple workers.
- **Update Idempotency**: Atomic claim on `telegram_idempotency` preventing duplicate bookings.

### Telegram Commands
| Command | Description |
|---|---|
| `/start` | Welcome banner, connection status, and primary navigation menu |
| `/help` | Detailed command and feature guide |
| `/hospitals` | List all active hospital branches with locations and contact info |
| `/doctors` | List active specialist doctors with qualifications and fees |
| `/specializations` | Browse medical departments and filter doctors |
| `/facilities` | View hospital facilities and emergency contacts |
| `/book` | Start deterministic 5-step appointment booking flow |
| `/my_appointments` | View scheduled visits and cancel upcoming appointments |
| `/my_prescriptions` | View medical diagnoses and download official prescription PDFs |
| `/link` | Link existing CityCare patient account via 6-digit OTP |
| `/register` | Register new patient account with consent and password setup link |
| `/status` | View verification status and linked profile |
| `/cancel` / `/reset` | Clear active flow and return to main menu |

### Running the Telegram Gateway

**Local Development (Polling Mode):**
```bash
python -m telegram_gateway.poller
# or
python run_telegram_poller.py
```

**Production (Webhook Mode):**
1. Configure in `.env`:
```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<your_token>
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://api.citycare.clinic/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=<your_secret_token>
TELEGRAM_TIMEZONE=Asia/Kolkata
```

2. Register webhook with Telegram Bot API:
```bash
python -m telegram_gateway.register_webhook
```

3. (Optional) Run standalone durable background queue worker:
```bash
python -m telegram_gateway.worker
```

---

## Automated Verification & Test Results

Run the complete backend test suite:

```bash
.\venv\Scripts\pytest -v
```

### Current Test Suite Status
- **Total Tests Executed**: **122**
- **Passed**: **122 (100%)**
- **Failed**: **0**
- **Test Modules**:
  - `tests/test_telegram_gateway.py`: 19 passed
  - `tests/test_patient_domain.py`: 12 passed
  - `tests/test_cli.py`: 40 passed
  - `tests/test_ai_chat.py`: 17 passed
  - `tests/test_appointments.py`: 8 passed
  - `tests/test_voicebot.py`: 6 passed
  - `tests/test_auth.py`: 6 passed
  - `tests/test_handbook_rag.py`: 5 passed
  - `tests/test_doctor.py`: 4 passed
  - `tests/test_prescription_rag.py`: 3 passed
  - `tests/test_prescriptions.py`: 2 passed


