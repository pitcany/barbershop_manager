# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system handles inbound SMS, booking/rescheduling, deposits/confirmations, cancellation filling from waitlist, and revenue tracking.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt
- **External Services**: Provider abstraction (real/mock) for Twilio, Stripe, SendGrid, Google Calendar

### Code Structure (Post-Refactor)
```
/app/backend/
  server.py          # Slim entry point (182 lines): app, CORS, startup, seed
  deps.py            # Shared: db, auth, rate limiting
  models.py          # Pydantic models
  routes/
    __init__.py      # Collects all sub-routers
    auth.py          # Auth, shop, dashboard, barbers, services, SMS/email test, health
    appointments.py  # Appointment CRUD, scheduling, availability
    clients.py       # Clients, conversations, waitlist
    payments.py      # Stripe payments, mock payment
    calendar.py      # Google Calendar OAuth, events
    jobs.py          # Scheduler jobs, reporting, audit, retention
    public.py        # Public endpoints (no auth)
    webhooks.py      # Twilio + Stripe webhooks
  providers/         # Provider abstraction (interfaces, mock, real)
  agents/            # Business logic agents
  scheduler.py       # APScheduler config
```

## Agent System
| Agent | Status | Description |
|-------|--------|-------------|
| FrontDeskAgent | Active | Handles inbound SMS, booking, template responses |
| NoShowEnforcementAgent | Active | Deposit requests, no-show detection |
| WaitlistFillAgent | Active | Finds matches, contacts waitlist clients |
| OwnerOpsAgent | Active | Daily summary emails to shop owner |
| RetentionRebookAgent | Active | Re-engages lapsed clients via email/SMS |

## What's Been Implemented

### Phase 1-5: Core MVP through RetentionRebookAgent (Feb 6-12)
- All database models + provider abstraction layer
- Agent system (FrontDesk, NoShow, Waitlist, OwnerOps, RetentionRebook)
- Admin auth, Dashboard, Conversations, Appointments, Waitlist, Settings
- SMS compliance, audit logging, revenue recovery tracking
- Scheduling Engine with conflict prevention
- Client Management Dashboard
- APScheduler background jobs
- Reporting + Jobs dashboards

### Phase 6: Stripe & Google Calendar Integrations (Feb 12)
- **Stripe Payments (REAL)**: Checkout sessions via emergentintegrations, payment_transactions collection, status polling, webhook handler
- **Google Calendar (REAL OAuth2)**: OAuth flow, token storage/refresh, event CRUD, freebusy availability
- Frontend: Pay Deposit button, Payment Success/Cancel pages, Integrations card in Settings

### Phase 7: server.py Refactor (Feb 12)
- Decomposed 2,555-line server.py into 8 focused route modules + shared deps.py
- server.py reduced to 182 lines (93% reduction)
- All 36 endpoints verified working (100% test pass rate)
- 4 bugs found and fixed during regression testing

## Integration Status
| Service | Status | Details |
|---------|--------|---------|
| SendGrid Email | **Active** | User-provided API key |
| Stripe Payments | **Active** | Using sk_test_emergent via emergentintegrations |
| Google Calendar | **Active** | OAuth2 with user-provided client credentials |
| Twilio SMS | Mocked | TWILIO_ENABLED=false, awaiting credentials |

## Prioritized Backlog

### P0 (Next)
- [ ] Client self-service booking portal (public-facing page for clients to book and pay)

### P1
- [ ] Enable Twilio for real SMS (pending credentials)
- [ ] Migrate APScheduler to Celery+Redis for production

### P2 (Future)
- [ ] Migrate MongoDB to PostgreSQL
- [ ] Multi-shop support

## Credentials
- **Admin**: username=admin, password=admin123
- **Preview**: https://booking-recovery.preview.emergentagent.com
