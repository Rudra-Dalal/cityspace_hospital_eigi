# CityCare Clinic

End-to-end appointment booking for a single-doctor clinic (Dr. Meera Kulkarni, CityCare Clinic, Dharampeth, Nagpur).

## Repositories in this workspace

| Folder | Stack |
|--------|--------|
| `citycare-backend/` | FastAPI · MongoDB (Motor) · JWT · pytest |
| `citycare-frontend/` | Vite · React (JS) · Tailwind · react-router-dom |

## Quick start

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
- API docs: http://localhost:8000/docs  

### Seeded doctor

Defaults from `.env.example`:

- Email: `doctor@citycare.clinic`
- Password: `Doctor@123`

## Tests

```bash
cd citycare-backend
.\venv\Scripts\Activate.ps1
pytest -v
```

## Prescriptions and patient assistant

Doctors accept booked appointments before creating one prescription per accepted appointment. The backend generates a real PDF, then uploads it to Cloudinary. Configure `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` in `citycare-backend/.env`.

The doctor only submits `appointment_id`, diagnosis, medicines, and general instructions; the patient, doctor, and hospital are derived from the appointment on the server. Patients retrieve only their own prescriptions at `GET /prescriptions/my`, doctors list what they issued at `GET /prescriptions/doctor`, and both download the stored PDF through the authorized `GET /prescriptions/{id}/download`. The patient assistant at `POST /patient-ai/chat` retrieves records filtered by the JWT-authenticated patient ID before Gemini receives any context. It provides prescription information only and never changes medication instructions.

See each folder’s README for endpoint tables, architecture notes, and viva prep.

For the backend command-line interface, see the [CityCare CLI Guide](CLI_GUIDE.md).

## Telephony VoiceBot

The backend includes a real-time Telephony VoiceBot layer (`POST /voice/incoming` and `WS /voice/ws`) powered by Twilio Media Streams, Pipecat, Deepgram STT, Gemini AI, and Sarvam TTS. Phone calls retrieve grounded answers to general clinic questions from the Handbook RAG. See `citycare-backend/README.md` for full ngrok setup and Twilio configuration.
