# CityCare Connect

Build a complete, beautiful frontend for CityCare — a multi-hospital healthcare appointment

booking platform. This connects to an existing FastAPI backend (I'll provide the base URL and endpoint contracts below) — do not invent different data shapes or endpoints.

http://localhost:8000

## Product & roles

Four roles, determined by the logged-in user's `role` field, each with its own experience:

- `customer` (patient): browse/book appointments, view & cancel their own appointments.

- `doctor`: view their schedule, appointment stats, and profile info.

- `hospital_manager`: manage their hospital's profile, view their doctors, view their hospital's appointments.

- `super_admin`: manage all hospitals (create/list/update status) and all users (create managers,

  create doctors, list/deactivate any user).

There is ONE shared login/signup flow. After login, the JWT response includes `access_token`

and a `user` object with a `role` field — redirect based on role:

customer → /patient/dashboard · doctor → /doctor/dashboard ·

hospital_manager → /manager/dashboard · super_admin → /admin/dashboard

Store the token and use it as a Bearer token on all authenticated requests. Protect each route

group so a user can't reach another role's pages.

## API contract (FastAPI backend)

- POST /auth/signup — {first_name, last_name, email, mobile, password} → user object

- POST /auth/login — {email, password} → {access_token, user: {id, first_name, last_name,

  email, mobile, role, hospital_id}}

- GET /appointments/free-slots?date=YYYY-MM-DD → {free_slots: [...]}

- POST /appointments — {date, slot, reason, temperature, symptoms[]} → created appointment

- GET /appointments/my → list of the current user's appointments

- PATCH /appointments/{id}/cancel → cancels an appointment

- GET /doctor/info, GET /doctor/schedule, GET /doctor/stats — doctor's own profile/schedule/stats

- GET /manager/hospital, PATCH /manager/hospital — manager's hospital profile

- GET /manager/doctors — doctors at the manager's hospital

- GET /manager/appointments — appointments at the manager's hospital

- POST /admin/hospitals, GET /admin/hospitals, PATCH /admin/hospitals/{id} — hospital CRUD

- POST /admin/users/manager, POST /admin/users/doctor — create manager/doctor (assigned to a

  hospital via hospital_id)

- GET /admin/users, PATCH /admin/users/{id}/deactivate — user management

## Screens to build

1. **Login** — email/password, link to signup, clean single-card layout.

2. **Signup** — first name, last name, email, mobile, password (patients only self-register).

3. **Patient dashboard** — upcoming appointments as cards (date, time slot, reason, status),

   cancel action, prominent "Book appointment" CTA.

4. **Book appointment** — date picker constrained to a 7-day window, a slot grid that loads

   free slots for the selected date, symptom multi-select (fever, cough, cold, bodyache,

   headache, other), temperature input, reason textarea, clear success/conflict states.

5. **Doctor dashboard** — today's/upcoming schedule in a clean table or timeline, key stats

   (e.g. appointments today, this week) as stat cards, doctor profile info.

6. **Hospital Manager dashboard** — hospital profile (editable), list of doctors at their

   hospital, list of hospital appointments — tabbed or sectioned layout.

7. **Super Admin dashboard** — tabbed: "Hospitals" (table with create/edit/status toggle) and

   "Users" (table with create manager/create doctor forms, list, deactivate action). This is

   the most data-dense screen — prioritize a clean table/filter pattern.

## Design direction

Healthcare product — calm, trustworthy, premium, NOT sterile-clinical and NOT generic-SaaS.

The current app uses a teal accent (#3493a3-ish) with a serif display font (Fraunces) over a

clean sans body (Source Sans) — you can keep this general direction (teal + editorial serif

headings feels distinct for healthcare) or propose something equally considered, but commit to

ONE accent color and ONE distinctive type pairing, not defaults. Generous whitespace, soft

shadows/rounded cards over hard borders, subtle motion on interactions (button states, card

hovers, slot selection, tab switches) — this should feel fluid, not static.

Build reusable components: buttons (primary/secondary), cards, form inputs with inline

validation states, status badges (booked/cancelled), data tables with empty/loading states,

a role-aware nav/sidebar. Fully responsive — patients will use this heavily on mobile.

Start with login/signup and the patient booking flow, then doctor dashboard, then manager and

admin dashboards.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/8764a40f-e6b6-41c0-8882-ce776ad746fa).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
