# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade multi-shop SaaS platform named "barbershop-autopilot" to reduce no-shows and recover lost revenue for barbershops. The system handles inbound SMS, booking/rescheduling, deposits/confirmations, cancellation filling from waitlist, and revenue tracking.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt (super_admin + shop_admin roles)
- **External Services**: Provider abstraction (real/mock) for Twilio, Stripe, SendGrid, Google Calendar

### Code Structure
```
/app/backend/
  server.py          # App init, CORS, startup, seed
  deps.py            # Shared: db, auth, rate limiting, get_super_admin
  models.py          # Pydantic models (Shop, Barber, Service, CRUD requests)
  routes/
    admin.py         # Super-admin: shop CRUD, shop admin CRUD
    auth.py          # Auth, shop details, dashboard, barbers/services CRUD, today-schedule
    appointments.py  # Appointment CRUD, scheduling, availability
    clients.py       # Clients, conversations, waitlist
    payments.py      # Stripe payments
    calendar.py      # Google Calendar OAuth
    jobs.py          # Scheduler jobs, reporting, audit, retention
    public.py        # Public booking portal + SMS consent
    webhooks.py      # Twilio + Stripe webhooks
  providers/         # Provider abstraction (interfaces, mock, real)
  agents/            # Business logic agents
/app/frontend/src/
  pages/
    SuperAdminPage.jsx         # Platform admin: manage shops + admins
    DashboardPage.jsx          # Dashboard with Today's Schedule + Booking Link
    AppointmentsPage.jsx       # Appointments list + New Appointment modal
    ManagePage.jsx             # Barber & Service CRUD
    SettingsPage.jsx           # Editable shop details, policies, booking link
    ClientsPage.jsx            # Client list
    BookingPage.jsx            # Public self-service booking wizard
    + other pages...
  components/layout/Layout.jsx  # Sidebar with role-based Platform Admin link
```

## What's Been Implemented

### Phase 1-8: Core MVP through Client Self-Service Booking
- All database models + provider abstraction layer
- Agent system (FrontDesk, NoShow, Waitlist, OwnerOps, RetentionRebook)
- Full admin dashboard with all management pages
- Stripe Payments (REAL), Google Calendar (REAL OAuth2), SendGrid Email (REAL)
- Client self-service booking portal at /book/:shopSlug
- server.py refactor into 8 modular route files

### Phase 9: Manager Workflow P0 Fixes
- "New Appointment" button on Appointments page
- Barber & Service Management page at /manage
- "Today's Schedule" timeline on Dashboard

### Phase 10: P1 Improvements
- Editable shop details in Settings
- Shareable booking link in Settings + Dashboard
- Removed MongoDB IDs from client list

### Phase 11: Super Admin Dashboard (Feb 20, 2026) — JUST COMPLETED
- **Platform Admin page** at `/admin` — list all shops, create new shops, view shop details
- **Shop admin management** — create admins per shop, list admins, password visibility toggle
- **Role-based navigation** — "Platform Admin" link visible only for super_admin users
- **Auto-slug generation** — shop name auto-generates URL slug
- **Booking link per shop** — copy booking link for any shop from admin panel
- **Backend already existed**: admin.py with shop CRUD + admin CRUD + role-based guards
- **DB fix**: Added `role: super_admin` to existing admin user (was missing from old seed)
- 100% test pass rate (16 backend + all frontend)

## Multi-Shop Architecture
- Every data model has `shop_id` for data isolation
- `super_admin` role for platform-level operations
- `shop_admin` role for shop-level operations
- Unique slug index for multi-tenancy
- Global username uniqueness (login resolves by username without shop context)
- Public booking via `/book/:shopSlug`

## Integration Status
| Service | Status | Details |
|---------|--------|---------|
| SendGrid Email | **Active** | User-provided API key |
| Stripe Payments | **Active** | Using emergent test key |
| Google Calendar | **Active** | OAuth2 with user-provided credentials |
| Twilio SMS | Mocked | TWILIO_ENABLED=false, awaiting credentials |

## Prioritized Backlog

### P1 (Next)
- [ ] Celery + Redis migration (replace APScheduler)
- [ ] Billing infrastructure (Stripe Connect — platform fee on deposits)
- [ ] Enable Twilio for real SMS (pending credentials)

### P2 (Future)
- [ ] MongoDB to PostgreSQL migration
- [ ] Enhanced multi-shop features (shop-level analytics, cross-shop reporting)

## Credentials
- **Super Admin**: username=admin, password=admin123 (role: super_admin)
- **Test Shop Admin**: testadmin7903 / TestAdmin123! (created during testing)
- **Public Booking**: /book or /book/:shopSlug
