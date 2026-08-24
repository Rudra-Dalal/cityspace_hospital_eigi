# CityCare Multi-Hospital Platform

Comprehensive multi-hospital healthcare management, patient appointment scheduling, prescription tracking, and AI-assisted care platform.

## Architecture

| Folder | Stack | Description |
|--------|-------|-------------|
| `citycare-backend/` | FastAPI · Motor (Async MongoDB) · JWT · Pytest | REST API, multi-tenant controllers, auth, doctor availability, RAG & VoiceBot |
| `citycare-frontend/` | Vite · React · TypeScript · TanStack Router & Query | Modern patient booking UI, role portals (Patient, Doctor, Manager, Admin) |

## Quick Start

### 1. MongoDB
```bash
docker run -d --name citycare-mongo -p 27017:27017 mongo:7
```
Or start your local MongoDB service (`net start MongoDB` on Windows).

### 2. Backend
```bash
cd citycare-backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd citycare-frontend
copy .env.example .env
npm install
npm run dev
```

- Frontend: http://localhost:5173
- Backend Swagger Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## Core Domain Capabilities

1. **Explicit Multi-Hospital & Doctor Selection**: Patients explicitly choose an active hospital branch, specialist doctor, date, and doctor-specific available slot without arbitrary fallbacks.
2. **Doctor-Specific Availability Model**: Computes real-time availability based on doctor assigned weekdays, configured time slots, and booked appointment subtraction.
3. **Reusable Registration Service**: Standardized patient registration with E.164 phone formatting (+91), password security, duplicate prevention, and strict customer role enforcement.
4. **Multi-Role Scoped Authorization**:
   - **Super Admin**: Manages hospitals (including activation status) and staff assignments.
   - **Hospital Manager**: Updates branch operational info (address, hours, facilities, contact); cannot modify status; accesses appointments and prescriptions strictly scoped to their hospital.
   - **Doctor**: Manages schedules, accepts appointments, generates prescriptions with PDF storage.
   - **Customer**: Manages own bookings and prescriptions with zero cross-tenant leakage.
   - **Deactivated Accounts**: Blocked with 401 Unauthorized across login and protected endpoints.
5. **No Double-Booking Guarantee**: Multi-tenant partial unique index `(hospital_id, doctor_id, date, slot)` for `status="booked"`.

---

## Automated Verification

Run all unit and integration tests in `citycare-backend`:

```bash
cd citycare-backend
.\venv\Scripts\pytest -v
```

Build the frontend client:

```bash
cd citycare-frontend
npm run build
```
