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

Change the seeded doctor and super-admin credentials in `.env` before first run. For deployment, set `APP_ENV=production`, use a unique random `SECRET_KEY` of at least 32 characters, set strong non-default seeded-account passwords, and configure explicit HTTPS origins in `CORS_ORIGINS`. The application refuses unsafe placeholder secrets, default account passwords, and localhost/wildcard CORS settings when production mode is enabled.

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

## Handbook RAG

The patient chatbot (`POST /patient-ai/chat`) incorporates a Handbook RAG pipeline for general clinic questions alongside personal prescription RAG:

```
PDF (CityCare-Clinic-Patient-Handbook.pdf)
 ↓
Extraction (pypdf)
 ↓
Chunking (Section & Policy aware)
 ↓
Embeddings (Gemini gemini-embedding-001 with fallback)
 ↓
MongoDB (handbook_chunks collection)
 ↓
Vector Search / Cosine Similarity
 ↓
Chatbot (Combined context)
 ↓
Gemini (Grounded answer)
```

### Ingestion command
```bash
python scripts/ingest_handbook.py
```

### MongoDB Atlas Vector Search Index (Optional for Atlas deployments)
```json
{
  "fields": [
    {
      "numDimensions": 3072,
      "path": "embedding",
      "similarity": "cosine",
      "type": "vector"
    }
  ]
}
```

## Telephony VoiceBot

The real-time Telephony VoiceBot layer allows patients to call the CityCare phone number and receive spoken, grounded answers to general clinic questions via Twilio Media Streams, Pipecat, Deepgram STT, Gemini AI, and Sarvam TTS:

```
Phone
 ↓
Twilio
 ↓
Twilio Media Stream
 ↓
WebSocket (/voice/ws)
 ↓
Pipecat (Silero VAD)
 ↓
Deepgram STT
 ↓
CityCare AI + Handbook RAG
 ↓
Gemini (Grounded voice system prompt)
 ↓
Sarvam TTS
 ↓
WebSocket
 ↓
Twilio
 ↓
Phone Speaker
```

### Telephony Environment Variables (`.env`)
```ini
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
PUBLIC_BASE_URL=https://your-ngrok-subdomain.ngrok-free.app

DEEPGRAM_API_KEY=your_deepgram_api_key
SARVAM_API_KEY=your_sarvam_api_key
```

### Local Development & ngrok Setup
1. **Start FastAPI Backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Expose Server via ngrok**:
   ```bash
   ngrok http 8000
   ```

3. **Configure `.env`**:
   Set `PUBLIC_BASE_URL=https://<your-ngrok-subdomain>.ngrok-free.app`

4. **Configure Twilio Voice Webhook**:
   - Webhook URL: `https://<your-ngrok-subdomain>.ngrok-free.app/voice/incoming`
   - HTTP Method: `POST`

5. **WebSocket Stream URL**:
   - `wss://<your-ngrok-subdomain>.ngrok-free.app/voice/ws`

### Security Limitation
- Incoming phone calls are **unauthenticated** by default.
- General clinic queries (hours, fees, cancellation, services) are answered from the authoritative Handbook RAG.
- Private patient prescription records will **never** be disclosed over phone calls without patient portal login.
- *Note: MCP tool execution is not part of this initial voice phase.*

## CityCare CLI Interface

A lightweight command-line interface built directly on top of the existing backend services and controllers. No HTTP server required — the CLI imports Python modules directly.

### Setup

The CLI runs from the `citycare-backend/` directory with the virtual environment activated:

```bash
# Windows PowerShell
.\\venv\\Scripts\\Activate.ps1

# macOS / Linux
# source venv/bin/activate
```

### Commands

| Command | Auth Required | Description |
|---------|:------------:|-------------|
| `health` | No | Check backend config and MongoDB connectivity |
| `doctors` | No | List clinic info and registered doctors |
| `appointments` | Yes | List your appointments (patients) or schedule (doctors/managers) |
| `prescriptions` | Yes (patient only) | List your prescriptions |
| `ask "<question>"` | Optional | Ask the CityCare AI a question |

### Authentication

Private commands (`appointments`, `prescriptions`) require a valid JWT token.  
Pass it with `--token <JWT>` or export it as an environment variable:

```bash
# Option 1: --token flag
python -m cli.main appointments --token eyJhbGci...

# Option 2: environment variable (recommended for scripting)
export CITYCARE_JWT_TOKEN=eyJhbGci...
python -m cli.main appointments
```

### Usage Examples

```bash
# Health check
python -m cli.main health
python -m cli.main health --json

# List clinic info and doctors
python -m cli.main doctors
python -m cli.main doctors --json

# My appointments (patient)
python -m cli.main appointments --token <JWT>
python -m cli.main appointments --token <JWT> --json

# Doctor / manager schedule
python -m cli.main appointments --token <DOCTOR_JWT>

# My prescriptions (patient only)
python -m cli.main prescriptions --token <JWT>
python -m cli.main prescriptions --token <JWT> --json

# Ask the AI (no auth — handbook answers only)
python -m cli.main ask "What are the consultation hours?"

# Ask the AI (with auth — includes personal prescription context)
python -m cli.main ask "What medicines was I prescribed?" --token <JWT>
python -m cli.main ask "What are the fees?" --json
```

### Output Modes

All commands support a `--json` flag for machine-readable output:
- Without `--json` — pretty human-readable table/text format.
- With `--json` — valid JSON to stdout, suitable for piping to `jq` or scripts.

### Unauthenticated Access

If `appointments` or `prescriptions` is called without a valid token, a clean message is returned and no data is exposed:

```
Authentication required to access patient appointments.
```

---

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
