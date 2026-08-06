# CityCare Clinic — Frontend

React (Vite + Tailwind) client for the CityCare Clinic FastAPI backend.

## Prerequisites

- Node.js 18+
- Backend running at `http://localhost:8000` (see `citycare-backend/README.md`)

## Setup

```bash
cd citycare-frontend
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
npm install
```

`.env`:

```
VITE_API_URL=http://localhost:8000
```

## Run

```bash
npm run dev
```

Open http://localhost:5173

## Build

```bash
npm run build
npm run preview
```

## Routes

| Path | Who |
|------|-----|
| `/login` | Public |
| `/signup` | Public (creates patient) |
| `/dashboard` | Patient |
| `/book` | Patient |
| `/doctor` | Doctor |

All API traffic goes through `src/api/client.js`. On HTTP 401 the client clears auth and redirects to `/login`.
