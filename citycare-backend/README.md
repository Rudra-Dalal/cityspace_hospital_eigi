# CityCare Clinic — Backend

Single-doctor appointment booking API built with **FastAPI** + **MongoDB** (Motor).

## Prerequisites

- Python 3.11+
- MongoDB 6+ running locally (or a reachable MongoDB URI)
- Git (optional)

### Start MongoDB (one command)

If MongoDB is installed as a Windows service:

```bash
net start MongoDB
```

Or with Docker:

```bash
docker run -d --name citycare-mongo -p 27017:27017 mongo:7
```

## Setup

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

Edit `.env` if needed (Mongo URI, JWT secret, doctor seed credentials).

## Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API base: http://localhost:8000  
- Interactive docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

## Seeded doctor login

On startup the API creates the doctor account from `.env` if missing:

| Field | Default (from `.env.example`) |
|-------|--------------------------------|
| Email | `doctor@citycare.clinic` |
| Password | `Doctor@123` |

Change `DOCTOR_EMAIL` / `DOCTOR_PASSWORD` in `.env` before first run if you want different credentials.

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | Public | Register patient (role always `patient`) |
| POST | `/auth/login` | Public | JWT + safe user info |
| GET | `/doctor/info` | Public | Clinic / doctor constants |
| GET | `/appointments/free-slots?date=` | Public | Free slots for date |
| POST | `/appointments` | Patient JWT | Book appointment |
| GET | `/appointments/my` | Patient JWT | Own appointments |
| GET | `/doctor/schedule?date=` | Doctor JWT | Day schedule |
| GET | `/doctor/stats` | Doctor JWT | Clinic stats |
| PATCH | `/appointments/{id}/cancel` | Owner or doctor | Cancel & free slot |

Errors consistently use `{"detail": "..."}`.

## How no-double-booking is guaranteed

1. **Polite pre-check** — before insert, query for an existing `booked` appointment on that `date` + `slot`.
2. **Steel door** — MongoDB **partial unique index** on `(date, slot)` where `status: "booked"`.
3. Concurrent inserts: only one wins; losers raise `DuplicateKeyError` → HTTP **409**.
4. Cancelling sets `status` to `cancelled`, so the partial index no longer covers that document and the slot is free again.

## Tests

```bash
# MongoDB must be running
pytest -v
```

Includes a concurrency test that fires multiple simultaneous bookings for the same slot and asserts exactly one `201`.

## Project layers

```
routes → controllers → cruds → MongoDB
schemas validate I/O   controllers enforce rules   cruds own queries
```

## Viva preparation (short)

- **Architecture**: thin routes, business rules in controllers, DB in CRUDs, Pydantic schemas at the door.
- **JWT**: signed token with `sub` (user id), `email`, `role`; expires in 1 hour; sent as `Authorization: Bearer …`.
- **401 vs 403**: 401 = missing/invalid/expired token (who are you?). 403 = valid token, wrong role (you may not).
- **Unique index**: database-level uniqueness that holds under race conditions.
- **Partial index**: uniqueness only for documents matching a filter (`status: booked`), so cancelled rows keep history but free the slot.
- **UTC**: `created_at` / `updated_at` stored in UTC so timezones do not skew records.
- **Frontend integration**: Vite on `:5173` allowed via CORS; frontend calls only this API through one client wrapper.
