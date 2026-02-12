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
  models.py          # Pydantic models (incl. barber/service CRUD models)
  routes/
    auth.py          # Auth, shop, dashboard, barbers CRUD, services CRUD, today-schedule
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
    DashboardPage.jsx          # Dashboard with Today's Schedule
    AppointmentsPage.jsx       # Appointments list + New Appointment modal
    ManagePage.jsx             # Barber & Service CRUD management
    BookingPage.jsx            # Public self-service booking wizard
    BookingConfirmationPage.jsx
    + existing admin pages...
  components/layout/Layout.jsx  # Sidebar navigation
```

## What's Been Implemented

### Phase 1-5: Core MVP through RetentionRebookAgent
- All database models + provider abstraction layer
- Agent system (FrontDesk, NoShow, Waitlist, OwnerOps, RetentionRebook)
- Admin auth, Dashboard, Conversations, Appointments, Waitlist, Settings
- SMS compliance, audit logging, revenue recovery tracking
- Scheduling Engine with conflict prevention
- Client Management Dashboard
- APScheduler background jobs
- Reporting + Jobs dashboards

### Phase 6: Stripe & Google Calendar Integrations
- **Stripe Payments (REAL)**: Checkout sessions, payment_transactions, status polling, webhook handler
- **Google Calendar (REAL OAuth2)**: OAuth flow, token storage/refresh, event CRUD, freebusy

### Phase 7: server.py Refactor
- Decomposed 2,555-line monolith into 8 route modules + shared deps.py

### Phase 8: Client Self-Service Booking Portal
- Public booking wizard at `/book`
- Smart deposit enforcement, Stripe checkout, client creation, calendar sync, rate limiting

### Phase 9: Manager Workflow Fixes (Feb 12, 2026) — JUST COMPLETED
- **"New Appointment" button** on Appointments page — dialog modal with client search, barber/service/date/time selection
- **Barber & Service Management page** at `/manage` — full CRUD (add/edit/delete) with tabs
- **"Today's Schedule" view** on Dashboard — timeline of day's appointments with time, client, service, barber, status
- **Backend CRUD endpoints**: POST/PATCH/DELETE for barbers and services
- **Navigation update**: Added "Manage Shop" to sidebar, reordered nav items
- 100% test pass rate (26 backend + all frontend tests)

## Integration Status
| Service | Status | Details |
|---------|--------|---------|
| SendGrid Email | **Active** | User-provided API key |
| Stripe Payments | **Active** | Using sk_test_emergent via emergentintegrations |
| Google Calendar | **Active** | OAuth2 with user-provided client credentials |
| Twilio SMS | Mocked | TWILIO_ENABLED=false, awaiting credentials |

## Prioritized Backlog

### P1 (Next)
- [ ] Editable shop details (phone, email, address) in Settings page
- [ ] Shareable booking link displayed in admin UI
- [ ] Hide internal MongoDB IDs from client list
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
