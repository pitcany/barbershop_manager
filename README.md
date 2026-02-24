# Barbershop Autopilot MVP

Production-grade MVP to reduce no-shows and recover lost revenue for barbershops with SMS workflows, deposit enforcement, waitlist fill, and admin reporting.

## Features

- SMS appointment management (BOOK, CONFIRM, CANCEL, STATUS, HELP)
- Deposit enforcement for no-show mitigation
- Waitlist fill automation when slots open
- Revenue recovery tracking and dashboard charts
- Admin dashboard for clients, appointments, policies, and operations

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Yarn
- MongoDB running locally

### Run locally

1. Backend:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8001
```

2. Frontend:
```bash
cd frontend
yarn install
yarn start
```

3. Access:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8001/api`
- API docs: `http://localhost:8001/docs`
- Admin login: `admin` / `admin123`

## SMS Compliance & Safety

- Outbound SMS requires explicit consent (`sms_consent=true`)
- Consent source and timestamp are stored
- STOP/UNSUBSCRIBE/CANCEL opt-out handling is enforced
- Integration side effects are audit logged in `integration_audit_log`
- Providers are mock-first and can be enabled per environment flags

## Provider Toggles

| Flag | Description |
|------|-------------|
| `TWILIO_ENABLED` | Enable real Twilio SMS sending |
| `STRIPE_ENABLED` | Enable Stripe checkout/payment flows |
| `STRIPE_CONNECT_ENABLED` | Enable Stripe Connect behavior for destination charges |
| `SEND_EMAILS` | Enable real SendGrid email sending |
| `CALENDAR_ENABLED` | Enable Google Calendar integration |

If a provider is disabled or misconfigured, the app falls back to mock providers where applicable.

## Stripe + Connect Notes

- Payment provider uses the official `stripe` Python SDK
- Stripe Connect support is included for connected account payouts and platform fees
- Shop policy/details include:
  - `stripe_connect_account_id`
  - `stripe_charges_enabled`
  - `stripe_payouts_enabled`
  - `platform_fee_bps`

## Configuration

Set backend environment variables (for example in `backend/.env`):

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=barbershop_autopilot
JWT_SECRET=your-secret-key
ADMIN_PASSWORD=admin123
CORS_ORIGINS=*

TWILIO_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

STRIPE_ENABLED=false
STRIPE_CONNECT_ENABLED=false
STRIPE_API_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

SEND_EMAILS=false
SENDGRID_API_KEY=
SENDER_EMAIL=

CALENDAR_ENABLED=false
GOOGLE_SERVICE_ACCOUNT_JSON=

REACT_APP_BACKEND_URL=http://localhost:8001
```

## SMS Simulation (No Twilio Required)

```bash
python scripts/simulate_sms.py --mode demo
python scripts/simulate_sms.py --mode interactive
python scripts/simulate_sms.py --mode test
```

## API Overview

The backend is modularized under `backend/routes/` and mounted at `/api`.

### Public

- `GET /api/public/s/{shop_slug}/shop-info`
- `GET /api/public/s/{shop_slug}/barbers`
- `GET /api/public/s/{shop_slug}/services`
- `GET /api/public/s/{shop_slug}/availability`
- `POST /api/public/s/{shop_slug}/book`
- `POST /api/public/s/{shop_slug}/sms-consent`
- Legacy compatibility routes remain available (for example `/api/public/shop-info`)

### Webhooks

- `POST /api/webhooks/twilio/inbound`
- `POST /api/webhooks/stripe`

### Auth/Admin Operations

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/dashboard/stats`
- `GET /api/dashboard/revenue-chart`
- `GET /api/appointments`
- `GET /api/clients`
- `GET /api/conversations`
- `GET /api/waitlist`
- `PATCH /api/shop/policy`
- `PATCH /api/shop/details`
- `GET /api/audit-log`
- `GET /api/reporting/overview`

See `/docs` for the complete live endpoint contract.

## Architecture

- FastAPI app in `backend/server.py`
- Route modules in `backend/routes/` (auth, appointments, clients, jobs, payments, public, webhooks, admin, calendar)
- Business logic agents in `backend/agents.py`
- Integration providers in `backend/providers/` with mock and real implementations
- Shared service layer in `backend/services/`
- MongoDB via Motor (direct queries, no ORM)

## Demo Data

Initial startup seeds demo entities including one shop, admin user, sample barbers/services/clients, and example appointments.

## Tech Stack

- Backend: FastAPI, Motor/MongoDB, Pydantic, JWT auth
- Frontend: React 19, Tailwind CSS, shadcn/ui, Recharts
- Payments: Stripe (optional, mock by default)
- SMS: Twilio (optional, mock by default)
- Email: SendGrid (optional, mock by default)

## License

Proprietary - All rights reserved.
