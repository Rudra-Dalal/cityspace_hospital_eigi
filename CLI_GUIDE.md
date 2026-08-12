# CityCare CLI Guide

This guide covers the command-line interface included with the CityCare backend.
The CLI calls the backend's Python services directly; it does not send requests
through the FastAPI server. MongoDB must still be running.

## 1. Prepare the backend

From the repository root, create and activate the backend environment, install
dependencies, and create the backend environment file:

### Windows PowerShell

```powershell
cd citycare-backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS/Linux

```bash
cd citycare-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` when necessary, especially `MONGODB_URI`, `MONGODB_DB_NAME`, and
the AI settings used by `ask`. Start MongoDB before using commands that access
the database. The CLI must be run from `citycare-backend/` so that Python can
import `cli` and `app`, and so `.env` is loaded.

## 2. Command format

The executable form used by this repository is:

```text
python -m cli.main <command> [options]
```

See all commands with:

```bash
python -m cli.main --help
```

Every command supports `--help`. Commands that return records also support
`--json`, which prints machine-readable JSON to stdout.

## 3. Commands

### `health`

Checks loaded backend configuration and whether MongoDB is reachable.

```bash
python -m cli.main health
python -m cli.main health --json
```

The human-readable output reports the clinic, environment, and database status.
The command reports an unavailable database cleanly instead of exposing a
traceback.

### `doctors`

Displays clinic details and registered doctor accounts. This command requires
MongoDB but does not require a JWT.

```bash
python -m cli.main doctors
python -m cli.main doctors --json
```

The JSON form contains `clinic_info` and a `doctors` array.

### `appointments`

Requires a valid JWT. The result depends on the authenticated role:

- Patients (`customer` or `patient`) see their own appointments.
- Doctors, hospital managers, and super admins see the upcoming schedule.

Pass a token directly:

```bash
python -m cli.main appointments --token "<JWT>"
python -m cli.main appointments --token "<JWT>" --json
```

Or set the token once in the environment:

```powershell
# Windows PowerShell
$env:CITYCARE_JWT_TOKEN = "<JWT>"
python -m cli.main appointments --json
```

```bash
# macOS/Linux
export CITYCARE_JWT_TOKEN="<JWT>"
python -m cli.main appointments --json
```

`--token` takes precedence over `CITYCARE_JWT_TOKEN`. The CLI does not print
appointment data when the token is missing, invalid, expired, or unauthorized.

### `prescriptions`

Requires a valid patient JWT and lists only that patient's prescriptions.
Doctor and manager tokens are rejected.

```bash
python -m cli.main prescriptions --token "<PATIENT_JWT>"
python -m cli.main prescriptions --token "<PATIENT_JWT>" --json
```

Human-readable output includes the date, doctor, diagnosis, medicine count, and
whether a PDF URL is available. JSON output contains the full serialized
prescription records returned by the service.

### `ask`

Asks the CityCare patient assistant a question. The question must be quoted if
it contains spaces.

General clinic questions can be asked without authentication:

```bash
python -m cli.main ask "What are the consultation hours?"
python -m cli.main ask "What are the consultation hours?" --json
```

Provide a patient JWT for questions that need personal prescription context:

```bash
python -m cli.main ask "What medicines was I prescribed?" --token "<PATIENT_JWT>"
```

The JSON response has `question`, `answer`, and `sources`. Without a token, the
assistant uses an anonymous user and can still answer handbook-grounded clinic
questions, but it cannot access personal prescription context.

## 4. Obtaining a JWT

The CLI intentionally has no login command. Obtain a token from the backend's
login endpoint, then pass it to a private command.

With the default seeded doctor account from `.env.example`:

```powershell
# Windows PowerShell
$login = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"doctor@citycare.clinic","password":"Doctor@123"}'
$env:CITYCARE_JWT_TOKEN = $login.access_token
```

```bash
# macOS/Linux with curl and jq
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"doctor@citycare.clinic","password":"Doctor@123"}' \
  | jq -r '.access_token')
export CITYCARE_JWT_TOKEN="$TOKEN"
```

The API must be running for these login examples. Change the sample credentials
before using them outside local development.

## 5. Useful scripting patterns

Use JSON when another tool will consume the result:

```bash
python -m cli.main doctors --json > doctors.json
python -m cli.main appointments --json | jq '.[].date'
python -m cli.main ask "What are the fees?" --json | jq -r '.answer'
```

The CLI returns exit code `1` for unexpected command errors and `130` when
interrupted with Ctrl+C. Authentication failures are presented as a normal
message and do not expose private records.

## 6. Troubleshooting

### `No module named cli` or `No module named app`

Run the command from `citycare-backend/` with its virtual environment active:

```bash
cd citycare-backend
python -m cli.main health
```

### Database is unavailable

Start MongoDB, confirm `MONGODB_URI` in `.env`, then retry:

```bash
python -m cli.main health
```

For Docker:

```bash
docker run -d --name citycare-mongo -p 27017:27017 mongo:7
```

### Authentication required

Check that the token is complete, has not expired, belongs to the expected
role, and is being passed in the same shell where it was exported. A token
provided with `--token` overrides the environment variable.

### AI command fails or has no useful answer

Check `GEMINI_API_KEY`, `GEMINI_ENABLED`, and the handbook data/configuration in
`.env`. The `ask` command also needs MongoDB because it loads handbook and
patient context through the backend services.

## Quick reference

| Purpose | Command |
|---|---|
| Show CLI help | `python -m cli.main --help` |
| Check configuration/database | `python -m cli.main health` |
| List clinic doctors | `python -m cli.main doctors` |
| List appointments | `python -m cli.main appointments --token <JWT>` |
| List patient prescriptions | `python -m cli.main prescriptions --token <JWT>` |
| Ask a clinic question | `python -m cli.main ask "<question>"` |
| Machine-readable output | Add `--json` |
