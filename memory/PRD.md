# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system handles inbound SMS, booking/rescheduling, deposits/confirmations, cancellation filling from waitlist, and revenue tracking.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt
- **External Services**: Provider abstraction (real/mock) for Twilio, Stripe, SendGrid, Google Calendar

### Code Structure
```
/app/backend/
  server.py          # Slim entry point: app, CORS, startup, seed
  deps.py            # Shared: db, auth, rate limiting
  models.py          # Pydantic models
  routes/
    auth.py          # Auth, shop details CRUD, dashboard, barbers CRUD, services CRUD, today-schedule
    appointments.py  # Appointment CRUD, scheduling, availability
    clients.py       # Clients, conversations, waitlist
    payments.py      # Stripe payments
    calendar.py      # Google Calendar OAuth, events
    jobs.py          # Scheduler jobs, reporting, audit, retention
    public.py        # Public booking portal + SMS consent + shop info
    webhooks.py      # Twilio + Stripe webhooks
  providers/         # Provider abstraction (interfaces, mock, real)
  agents/            # Business logic agents
  scheduler.py       # APScheduler config
/app/frontend/src/
  pages/
    DashboardPage.jsx          # Dashboard with Today's Schedule + Booking Link
    AppointmentsPage.jsx       # Appointments list + New Appointment modal
    ManagePage.jsx             # Barber & Service CRUD management
    SettingsPage.jsx           # Editable shop details, policies, booking link, integrations
    ClientsPage.jsx            # Client list (no MongoDB IDs)
    BookingPage.jsx            # Public self-service booking wizard
    BookingConfirmationPage.jsx
    + other admin pages...
  components/layout/Layout.jsx  # Sidebar navigation
```

## What's Been Implemented

### Phase 1-5: Core MVP through RetentionRebookAgent
- All database models + provider abstraction layer
- Agent system (FrontDesk, NoShow, Waitlist, OwnerOps, RetentionRebook)
- Admin auth, Dashboard, Conversations, Appointments, Waitlist, Settings
- SMS compliance, audit logging, revenue recovery tracking
- Scheduling Engine with conflict prevention
- Client Management Dashboard, APScheduler background jobs, Reporting + Jobs dashboards

### Phase 6: Stripe & Google Calendar Integrations
- **Stripe Payments (REAL)**: Checkout sessions, transactions, status polling, webhook
- **Google Calendar (REAL OAuth2)**: OAuth flow, token storage/refresh, event CRUD

### Phase 7: server.py Refactor
- Decomposed 2,555-line monolith into 8 route modules + shared deps.py

### Phase 8: Client Self-Service Booking Portal
- Public booking wizard at `/book`, smart deposit enforcement, Stripe checkout, calendar sync

### Phase 9: Manager Workflow P0 Fixes (Feb 12, 2026)
- "New Appointment" button on Appointments page
- Barber & Service Management page at `/manage` with full CRUD
- "Today's Schedule" timeline on Dashboard
- 100% test pass rate (26 backend + all frontend)

### Phase 10: P1 Improvements (Feb 12, 2026) — JUST COMPLETED
- **Editable shop details** in Settings (name, phone, email, address) via PATCH /api/shop/details
- **Shareable booking link** in Settings + Dashboard with copy-to-clipboard
- **Removed MongoDB IDs** from client list — shows appointment count instead
- 100% test pass rate (11 backend + all frontend)

## Integration Status
| Service | Status | Details |
|---------|--------|---------|
| SendGrid Email | **Active** | User-provided API key |
| Stripe Payments | **Active** | Using sk_test_emergent via emergentintegrations |
| Google Calendar | **Active** | OAuth2 with user-provided client credentials |
| Twilio SMS | Mocked | TWILIO_ENABLED=false, awaiting credentials |

## Prioritized Backlog

### P1 (Next)
- [ ] Enable Twilio for real SMS (pending credentials)
- [ ] Migrate APScheduler to Celery+Redis for production
- [ ] Billing infrastructure (Stripe Connect for platform fee on deposits)

### P2 (Future)
- [ ] Migrate MongoDB to PostgreSQL
- [ ] Multi-shop support

## Credentials
- **Admin**: username=admin, password=admin123
- **Public Booking**: /book
- **Admin Dashboard**: /login
