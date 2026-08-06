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

See each folder’s README for endpoint tables, architecture notes, and viva prep.
