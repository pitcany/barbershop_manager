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
  server.py          # Slim entry point (182 lines): app, CORS, startup, seed
  deps.py            # Shared: db, auth, rate limiting
  models.py          # Pydantic models
  routes/
    auth.py          # Auth, shop, dashboard, barbers, services, SMS/email test, health
    appointments.py  # Appointment CRUD, scheduling, availability
    clients.py       # Clients, conversations, waitlist
    payments.py      # Stripe payments, mock payment
    calendar.py      # Google Calendar OAuth, events
    jobs.py          # Scheduler jobs, reporting, audit, retention
    public.py        # Public booking portal + SMS consent + shop info
    webhooks.py      # Twilio + Stripe webhooks
  providers/         # Provider abstraction (interfaces, mock, real)
  agents/            # Business logic agents
  scheduler.py       # APScheduler config
/app/frontend/src/pages/
  BookingPage.jsx            # Public self-service booking wizard
  BookingConfirmationPage.jsx # Post-payment confirmation
  + existing admin pages...
```

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
- **Stripe Payments (REAL)**: Checkout sessions, payment_transactions, status polling, webhook handler
- **Google Calendar (REAL OAuth2)**: OAuth flow, token storage/refresh, event CRUD, freebusy

### Phase 7: server.py Refactor (Feb 12)
- Decomposed 2,555-line monolith into 8 route modules + shared deps.py (93% reduction)

### Phase 8: Client Self-Service Booking Portal (Feb 12)
- **Public booking wizard** at `/book`: Service → Barber → Date/Time → Info → Confirm
- **Smart deposit enforcement**: Required when booking within 48h or client has no-show history
- **Stripe checkout integration**: Redirects to Stripe when deposit required, then to `/book/confirmation`
- **Client creation**: Auto-creates or updates client record from phone number
- **Calendar sync**: Appointments booked via portal auto-create Google Calendar events
- **Rate limiting**: 10 bookings per IP per hour
- Public API endpoints: `/api/public/barbers`, `/api/public/services`, `/api/public/availability`, `/api/public/book`, `/api/public/appointment/{id}`
- 100% test pass rate (29/29 backend + all frontend tests)

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
- **Public Booking**: https://booking-recovery.preview.emergentagent.com/book
- **Admin Dashboard**: https://booking-recovery.preview.emergentagent.com/login
