---
name: testing-citycare
description: How to run and end-to-end test the CityCare hospital platform (FastAPI backend + TanStack Start frontend) locally, including the prescription/PDF flow.
---

# Testing CityCare locally

## Services

1. **MongoDB** — run in docker: `docker run -d --name citycare-mongo -p 27017:27017 mongo:7`.
   Inspect data with `docker exec citycare-mongo mongosh citycare --quiet --eval '...'`.
2. **Backend** — `citycare-backend/venv/bin/python -m uvicorn app.main:app --port 8000`.
   Start it detached with `setsid nohup ... &` — plain `nohup ... &` from the exec tool gets
   killed when the shell call ends.
   On startup it seeds a doctor, a super-admin and (via migrations) a "CityCare Clinic" hospital,
   and assigns the doctor to it. No manual seeding needed.
3. **Frontend** — use bun (`~/.bun/bin/bun run dev`); npm's rolldown binding may be broken.
   The Lovable vite config **forces port 8080** and ignores `--port`. The backend's default
   `CORS_ORIGINS` in `.env` is `http://localhost:5173`, so start the backend with
   `CORS_ORIGINS="http://localhost:8080,http://localhost:5173"` or the UI's API calls fail.

## Accounts

- Doctor: `doctor@citycare.clinic` / `Doctor@123` (from `.env`, seeded on startup).
- Super admin: `admin@citycare.clinic` / `Admin@123`.
- Patients: self-signup at `/signup`, then sign in at `/`.

## UI paths

- Patient books at `/patient/book` (pick day → free slot → symptom chip → temperature 90–115 →
  reason ≥5 chars → Confirm appointment).
- Doctor at `/doctor/dashboard`: "Accept" on a booked appointment; once accepted a
  "Create Prescription" button appears inline on the appointment card, plus a
  "Prescriptions issued" panel lower on the page.
- Patient at `/patient/dashboard`: "My prescriptions" panel with View / Download PDF.

## Cloudinary (prescription PDFs)

`POST /prescriptions` generates a PDF and uploads it to Cloudinary **before** inserting the Mongo
document. If `CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET` are empty in `citycare-backend/.env`,
creation fails with HTTP 503 "Prescription PDF storage is temporarily unavailable." and nothing is
stored — the flow cannot be tested at all.

Fallback when credentials are unavailable (report clearly that this was stubbed): run the backend
via a small wrapper script that keeps all repo code intact and only replaces the upload boundary:

```python
import sys; sys.path.insert(0, "<repo>/citycare-backend")
import app.services.cloudinary_service as cs
import app.controllers.prescription_controller as pc
def _local_upload(pdf_bytes, prescription_id):
    open(f"/tmp/citycare_pdfs/p_{prescription_id}.pdf", "wb").write(pdf_bytes)
    return f"http://127.0.0.1:8100/p_{prescription_id}.pdf", f"local/{prescription_id}"
cs.upload_prescription_pdf = pc.upload_prescription_pdf = _local_upload
import uvicorn; uvicorn.run("app.main:app", port=8000)
```
Serve `/tmp/citycare_pdfs` with `python3 -m http.server 8100 --bind 127.0.0.1`; the real
`GET /prescriptions/{id}/download` then re-fetches over HTTP exactly like it would from Cloudinary.
Note `pc` must be patched too — the controller imports the function by name.

## Devin Secrets Needed

- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — for unstubbed
  prescription PDF upload testing.

## Known pitfalls when verifying downloads

- Downloaded filenames come from the `Content-Disposition` header. Because the SPA is cross-origin
  (`:8080` → `:8000`) and the backend's `CORSMiddleware` has no `expose_headers`, the browser
  cannot read that header and files land as the fallback `prescription.pdf`. Verify the real
  header with a direct authenticated request; adding
  `expose_headers=["Content-Disposition"]` is the likely fix.
- Prescription PDFs are uploaded with `public_id = appointment_id` and `overwrite=True` *before*
  the unique-index insert, so a rejected duplicate creation can still overwrite the stored PDF of
  the existing prescription. Always re-download the PDF *after* any duplicate/error attempt and
  diff the content, not just the HTTP status.
