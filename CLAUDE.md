# Barbershop Autopilot MVP

A production-grade system to reduce no-shows and recover lost revenue for barbershops. Handles SMS appointment management, deposit enforcement, waitlist filling, and revenue tracking through an admin dashboard.

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Backend | FastAPI | 0.110.x | Async Python web framework |
| Frontend | React | 19.x | SPA with CRA (via CRACO) |
| Database | MongoDB | — | Document store via Motor (async) |
| Styling | Tailwind CSS | 3.x | Utility-first CSS with CSS variables |
| Components | shadcn/ui (Radix) | — | Accessible component primitives |
| Charts | Recharts | 3.x | Dashboard data visualization |
| Forms | React Hook Form + Zod | — | Form state + schema validation |
| SMS | Twilio | 9.x | Optional, mock by default |
| Payments | Stripe | 14.x | Optional, mock by default |
| Email | SendGrid | 6.x | Optional, mock by default |
| Auth | JWT + bcrypt | — | Bearer token auth |

## Quick Start

```bash
# Prerequisites: Python 3.11+, Node.js 18+, Yarn, MongoDB running locally

# One-command setup
./dev.sh install   # Creates venv in backend/.venv, installs all deps
./dev.sh start     # Starts backend + frontend, streams logs, Ctrl+C to stop

# Or manually:
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8001
# (in separate terminal)
cd frontend && yarn install && yarn start

# Access
# Frontend: http://localhost:3000
# Backend API: http://localhost:8001/api
# Admin login: admin / admin123
```

## Project Structure

```
barbershop_manager/
├── backend/
│   ├── server.py              # FastAPI app — middleware, startup/shutdown, seed data
│   ├── deps.py                # Shared dependencies: db, auth, rate limiting
│   ├── models.py              # Pydantic models, enums, DTOs
│   ├── agents.py              # Business logic: FrontDesk, NoShowEnforcement, WaitlistFill
│   ├── sms_compliance.py      # SMS consent enforcement, opt-out handling
│   ├── audit.py               # Integration audit logger (all external API calls)
│   ├── revenue_logger.py      # Internal revenue attribution tracking
│   ├── scheduled_jobs.py      # Appointment reminder job (cron-compatible)
│   ├── requirements.txt       # Python dependencies
│   ├── routes/
│   │   ├── __init__.py        # Collects all sub-routers into all_routers list
│   │   ├── auth.py            # Auth, shop, dashboard, barbers, services, health
│   │   ├── appointments.py    # Appointment CRUD and status updates
│   │   ├── clients.py         # Client listing and search
│   │   ├── payments.py        # Payment and deposit endpoints
│   │   ├── calendar.py        # Calendar integration endpoints
│   │   ├── jobs.py            # Scheduled job triggers
│   │   ├── public.py          # Public endpoints (no auth): booking, consent, availability
│   │   └── webhooks.py        # Twilio inbound SMS + Stripe webhook handlers
│   └── providers/
│       ├── __init__.py        # Provider factory + singleton getters
│       ├── interfaces.py      # Abstract base classes (SMS, Calendar, Email, Payment)
│       ├── mock_providers.py  # In-memory mocks for local dev
│       └── real_providers.py  # Twilio, Stripe, SendGrid, Google Calendar
├── frontend/
│   ├── src/
│   │   ├── App.js             # Routes, AuthContext, axios interceptors
│   │   ├── pages/             # 7 page components (PascalCase.jsx)
│   │   ├── components/
│   │   │   ├── ui/            # 46 shadcn/ui components (kebab-case.jsx)
│   │   │   └── layout/        # Layout.jsx — sidebar navigation
│   │   ├── hooks/             # use-toast.js
│   │   └── lib/               # utils.js (cn() helper)
│   ├── package.json           # Yarn, React 19, shadcn/ui
│   ├── tailwind.config.js     # Dark theme, CSS variables, custom fonts
│   └── craco.config.js        # Webpack alias (@/ -> src/)
├── scripts/
│   └── simulate_sms.py        # SMS testing without Twilio (demo/interactive/test)
├── design_guidelines.json     # Design system: colors, fonts, spacing
├── memory/
│   └── PRD.md                 # Product requirements document
└── backend_test.py            # API integration test suite
```

## Architecture Overview

The system uses a **provider abstraction pattern** where all external services (Twilio, Stripe, SendGrid, Google Calendar) have mock implementations used by default. Real providers activate when environment flags are set and credentials are present — no API keys needed for local development.

Three **deterministic agents** handle business logic (no LLM calls):
- **FrontDeskAgent**: Processes inbound SMS commands (BOOK, CONFIRM, CANCEL, STATUS, HELP)
- **NoShowEnforcementAgent**: Deposit requirements, no-show tracking, payment link creation
- **WaitlistFillAgent**: Matches cancelled slots to waitlist entries, sends offers via SMS

All external side effects are logged to the `integration_audit_log` collection for compliance.

```
┌──────────┐     ┌────────────────┐     ┌──────────────┐
│ React UI │ ──▶ │  FastAPI API   │ ──▶ │   MongoDB    │
└──────────┘     │  (server.py)   │     └──────────────┘
                 │                │
                 │  ┌──────────┐  │     ┌──────────────┐
                 │  │  Agents  │──│──▶  │  Providers   │
                 │  └──────────┘  │     │ (mock/real)  │
                 └────────────────┘     └──────────────┘
```

### Key Modules

| Module | Location | Purpose |
|--------|----------|---------|
| App Entry Point | `backend/server.py` | FastAPI app, CORS, startup/shutdown, seed data |
| Shared Deps | `backend/deps.py` | DB connection, JWT auth, rate limiting, query utilities |
| Route Modules | `backend/routes/*.py` | API endpoints split by domain (auth, appointments, clients, etc.) |
| Data Models | `backend/models.py` | Pydantic models, enums (AppointmentStatus has 8 states) |
| SMS Compliance | `backend/sms_compliance.py` | Consent checks, STOP/opt-out handling, compliant sending |
| Audit Logger | `backend/audit.py` | Logs all external API calls (never blocks main operations) |
| Provider Factory | `backend/providers/__init__.py` | Environment-based provider selection with singleton caching |
| Auth Context | `frontend/src/App.js` | React Context for auth, axios interceptors |
| Design System | `design_guidelines.json` | Colors, fonts, component styling reference |

## Development Guidelines

### Backend Naming

| What | Convention | Example |
|------|-----------|---------|
| Files | snake_case | `sms_compliance.py`, `revenue_logger.py` |
| Classes | PascalCase | `FrontDeskAgent`, `SMSComplianceService` |
| Functions | snake_case | `create_access_token()`, `process_inbound_message()` |
| Constants | UPPER_SNAKE_CASE | `OPT_OUT_KEYWORDS`, `SECRET_KEY` |
| Enums | PascalCase class, UPPER values | `AppointmentStatus.CONFIRMED` |
| DB collections | snake_case plural | `appointments`, `integration_audit_log` |
| API routes | kebab-case | `/api/sms-consent`, `/api/email-outbox` |

### Frontend Naming

| What | Convention | Example |
|------|-----------|---------|
| Page files | PascalCase.jsx | `DashboardPage.jsx`, `ConversationsPage.jsx` |
| UI component files | kebab-case.jsx | `button.jsx`, `dropdown-menu.jsx` (shadcn) |
| Layout files | PascalCase.jsx | `Layout.jsx` |
| Hook files | kebab-case.js | `use-toast.js` |
| Component names | PascalCase | `export default function DashboardPage()` |
| Variables/functions | camelCase | `fetchAppointments`, `setLoading` |
| Constants | SCREAMING_SNAKE | `BACKEND_URL`, `TOAST_LIMIT` |
| API data keys | snake_case | `deposit_amount`, `confirmation_window_hours` |
| CSS classes | Tailwind utilities | `bg-card border-border text-primary` |

### Import Aliases

- Backend: standard Python relative/absolute imports
- Frontend: `@/` maps to `src/` (configured in `jsconfig.json` and `craco.config.js`)

### Key Patterns

- **Modular routes**: API endpoints live in `backend/routes/*.py`, registered via `routes/__init__.py`; `server.py` is the slim entry point (app, middleware, startup, seed)
- **UUID string IDs**: `str(uuid.uuid4())` instead of MongoDB ObjectIds
- **ISO timestamp strings**: Dates stored as ISO strings, not datetime objects
- **Projection excludes _id**: All MongoDB queries use `{"_id": 0}`
- **Pydantic extra="ignore"**: Models ignore extra MongoDB fields
- **Non-blocking audit/revenue**: Failures in logging never block main operations
- **Mock by default**: All providers default to mock implementations
- **No ORM**: Direct Motor/PyMongo usage with Pydantic for validation
- **Context API only**: No Redux/Zustand — auth via React Context, rest is local state
- **Direct axios calls**: No service layer — components call `axios.get(`${API}/endpoint`)` directly

## Available Commands

| Command | Description |
|---------|-------------|
| `./dev.sh start` | Start backend + frontend (streams logs, Ctrl+C to stop) |
| `./dev.sh stop` | Stop running dev servers |
| `./dev.sh restart` | Stop then start dev servers |
| `./dev.sh status` | Show whether dev servers are running |
| `./dev.sh install` | Create venv and install all dependencies |
| `./dev.sh reseed` | Drop database and restart with fresh demo data |
| `yarn start` | Start frontend dev server (from `frontend/`) |
| `yarn build` | Production build (from `frontend/`) |
| `python scripts/simulate_sms.py --mode demo` | Demo SMS conversation |
| `python scripts/simulate_sms.py --mode interactive` | Interactive SMS testing |
| `python scripts/simulate_sms.py --mode test` | Test all SMS commands |
| `python -m pytest` | Run backend tests |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGO_URL` | No | `mongodb://localhost:27017` | MongoDB connection |
| `DB_NAME` | No | `barbershop_autopilot` | Database name |
| `JWT_SECRET` | Yes (prod) | `barbershop-autopilot-secret-key-...` | JWT signing key |
| `ADMIN_PASSWORD` | No | `admin123` | Initial admin password |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `TWILIO_ENABLED` | No | `false` | Enable real SMS |
| `TWILIO_ACCOUNT_SID` | If Twilio | — | Twilio credentials |
| `TWILIO_AUTH_TOKEN` | If Twilio | — | Twilio credentials |
| `TWILIO_PHONE_NUMBER` | If Twilio | — | Twilio from number |
| `STRIPE_API_KEY` | No | — | Stripe key (auto-enables if set) |
| `SEND_EMAILS` | No | `false` | Enable real email |
| `SENDGRID_API_KEY` | If email | — | SendGrid credentials |
| `SENDER_EMAIL` | If email | — | From email address |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | — | Path to Google Calendar creds |
| `REACT_APP_BACKEND_URL` | Yes | — | Backend URL for frontend |

## Troubleshooting

### `passlib` + `bcrypt` crash on Python 3.13+

`passlib` 1.7.4 is unmaintained and incompatible with `bcrypt` >= 4.2 on newer Python versions. Symptoms: `ValueError: password cannot be longer than 72 bytes` during startup, or `AttributeError: module 'bcrypt' has no attribute '__about__'`.

**Fix:** After installing requirements, pin bcrypt:
```bash
backend/.venv/bin/pip install 'bcrypt==4.1.3'
```

### `emergentintegrations` not found during `pip install`

`requirements.txt` includes `emergentintegrations==0.1.0` which is not on PyPI. This causes `pip install -r requirements.txt` to fail and roll back all installs.

**Fix:** Install without it:
```bash
grep -v emergentintegrations backend/requirements.txt | backend/.venv/bin/pip install -r /dev/stdin
backend/.venv/bin/pip install 'bcrypt==4.1.3'
```

### Login fails with `admin / admin123`

Seed data only runs when the `shops` collection is empty. If a previous startup crashed mid-seed (e.g., due to the bcrypt issue above), the shop exists but the admin user doesn't — and re-seeding is skipped on subsequent starts.

**Fix:** Drop the database and restart:
```bash
mongosh --quiet --eval 'db.getMongo().getDB("barbershop_autopilot").dropDatabase()'
./dev.sh restart
```

## API Endpoints

### Public (no auth)
- `POST /api/public/sms-consent` — SMS consent form
- `GET /api/public/shop-info` — Shop information

### Webhooks (no auth)
- `POST /api/webhooks/twilio/inbound` — Inbound SMS handler
- `POST /api/webhooks/stripe` — Stripe payment events

### Auth
- `POST /api/auth/login` — Returns JWT token
- `GET /api/auth/me` — Current user info

### Dashboard
- `GET /api/dashboard/stats` — Summary statistics
- `GET /api/dashboard/revenue-chart` — 30-day revenue data

### Resources (auth required)
- `GET /api/appointments` — List with filters, pagination
- `PATCH /api/appointments/{id}/status` — Update status
- `GET /api/conversations` — Grouped by client
- `GET /api/clients` — List with search
- `GET /api/waitlist` — Active entries
- `GET /api/barbers` — Active barbers
- `GET /api/services` — Available services
- `PATCH /api/shop/policy` — Update shop policies
- `GET /api/audit-log` — Integration audit trail

## MongoDB Collections

`shops`, `admin_users`, `barbers`, `services`, `clients`, `appointments`, `messages`, `waitlist`, `payments`, `events`, `email_outbox`, `integration_audit_log`, `recovered_revenue_events`

## Design System

Dark theme with gold accents. See `design_guidelines.json` for full spec.
- **Primary**: Gold (#D4AF37)
- **Background**: Near-black (#09090b)
- **Fonts**: Playfair Display (headings), Inter (body), JetBrains Mono (code/numbers)
- **Aesthetic**: "Old Money Tech / Modern Barbershop"
- **Components**: shadcn/ui New York style with CSS variable theming


## Skill Usage Guide

When working on tasks involving these technologies, invoke the corresponding skill:

| Skill | Invoke When |
|-------|-------------|
| tailwind | Applies Tailwind CSS utility classes with CSS variables and dark theme |
| fastapi | Builds FastAPI endpoints, async handlers, JWT auth, and middleware configuration |
| mongodb | Designs MongoDB schemas, writes Motor async queries, and manages collections |
| twilio | Implements Twilio SMS sending, inbound webhooks, and compliance handling |
| stripe | Integrates Stripe payment processing, webhooks, and deposit enforcement |
| react | Manages React 19 components, hooks, Context API auth, and state patterns |
| sendgrid | Configures SendGrid email delivery and outbox management |
| recharts | Builds dashboard data visualizations with Recharts components |
| frontend-design | Creates React UI with shadcn/ui, Tailwind styling, and gold-accented dark theme |
| shadcn-ui | Implements accessible shadcn/ui components with Radix primitives |
| python | Writes Python async code, Pydantic models, and business logic agents |
| react-hook-form | Manages form state with React Hook Form and Zod schema validation |
| pydantic | Defines Pydantic models, DTOs, and API request/response validation |
| jwt | Implements JWT token generation, validation, and bearer auth |
| axios | Configures axios HTTP client, interceptors, and API request patterns |
