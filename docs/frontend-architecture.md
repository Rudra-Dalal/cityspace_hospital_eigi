# Medihub / CityCare Frontend Architecture

## 1. Directory Structure

```
citycare-frontend/
├── src/
│   ├── components/
│   │   ├── ai/                      # AI Assistants (Doctor AI, Patient Prescription AI)
│   │   ├── prescriptions/           # Clinical Prescription Writer & Viewers
│   │   ├── ui/                      # Radix/shadcn UI accessible primitives
│   │   ├── ui-kit.tsx               # Shared high-level Medihub cards, badges, panels, headers
│   │   ├── AppShell.tsx             # Global desktop & mobile application shell
│   │   ├── Field.tsx                # Form field label, error, and helper container
│   │   ├── RoleGate.tsx             # Role-based route guard
│   │   └── ThemeToggle.tsx          # Light / Dark / System theme switcher
│   ├── hooks/                       # Reusable hooks (useMobile, etc.)
│   ├── lib/
│   │   ├── api.ts                   # Typesafe API client, data models, error parser
│   │   ├── auth.tsx                 # Auth context & session management
│   │   ├── format.ts                # Date, currency, name, slot formatters
│   │   ├── theme.tsx                # ThemeProvider (Light / Dark / System)
│   │   └── utils.ts                 # cn (clsx + tailwind-merge)
│   ├── routes/                      # TanStack file-based routes
│   │   ├── __root.tsx               # Root document shell, providers & error boundary
│   │   ├── index.tsx                # Landing & Sign-in
│   │   ├── signup.tsx               # Patient onboarding
│   │   ├── patient.dashboard.tsx    # Patient consultation overview & prescription vault
│   │   ├── patient.book.tsx         # 5-step guided specialist booking flow
│   │   ├── doctor.dashboard.tsx     # Doctor clinical schedule & queue
│   │   ├── manager.dashboard.tsx    # Hospital branch operations
│   │   └── admin.dashboard.tsx      # Super admin network management
│   └── styles.css                   # Tailwind v4 engine, tokens, typography & utilities
```

---

## 2. Server State & Data Flow Strategy

1. **Source of Truth**: The FastAPI backend is the sole source of truth for doctor schedules, slot availability, appointments, and prescriptions.
2. **TanStack Query Layer**:
   - Cache keys are strictly namespaced: `['appointments', 'my']`, `['doctor-availability', doctorId, date]`, `['active-hospitals']`, `['active-doctors', hospitalId]`.
   - Mutation side-effects explicitly trigger targeted query invalidation to maintain cache coherence.
3. **No False Optimism**: High-stakes healthcare actions (booking, cancellations, issuing prescriptions) display loading indicators and resolve strictly on server confirmation.

---

## 3. Preparation for Future Multi-Channel Interface (e.g. Telegram)

The frontend cleanly interacts with backend services without storing proprietary business logic in the client:
- Doctor slot computation and booking conflict logic lives in the backend.
- Prescription generation and Cloudinary PDF asset management remain server-orchestrated.
- AI assistant responses come directly from the backend agent gateway.
This ensures future Telegram bot or mobile interfaces will have 100% parity with the web experience.
