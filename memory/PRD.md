# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade multi-shop SaaS platform named "barbershop-autopilot" to reduce no-shows and recover lost revenue for barbershops. The system handles inbound SMS, booking/rescheduling, deposits/confirmations, cancellation filling from waitlist, and revenue tracking.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt (super_admin + shop_admin roles)
- **Multi-tenancy**: Every model has shop_id, unique slug index, global username uniqueness

### Code Structure
```
/app/backend/
  server.py, deps.py, models.py
  routes/ (admin.py, auth.py, appointments.py, clients.py, payments.py, calendar.py, jobs.py, public.py, webhooks.py)
  providers/, agents/, scheduler.py
/app/frontend/src/
  pages/ (SuperAdminPage, DashboardPage, AppointmentsPage, ManagePage, SettingsPage, ClientsPage, BookingPage, etc.)
  components/layout/Layout.jsx
```

## Completed Features

### Core MVP (Phases 1-8)
- Agent system, scheduling engine, client management, waitlist
- Stripe Payments (REAL), Google Calendar (REAL OAuth2), SendGrid Email (REAL)
- Client self-service booking at /book/:shopSlug
- Modular backend (8 route files)

### Manager Workflow Fixes (Phase 9-10)
- New Appointment button, Barber/Service CRUD, Today's Schedule, editable shop details, booking link, cleaned client list

### Multi-Shop Platform Admin (Phase 11-12, Feb 20 2026) — LATEST
- **Platform Overview Dashboard** — aggregate stats (total shops, 30d appointments, revenue, no-show rate)
- **Per-Shop Performance Table** — breakdown by shop (clients, appointments, no-shows, revenue)
- **Shop Management** — create/list shops, view details, copy booking links
- **Admin Management** — create/list shop admins per shop
- **Role-based UI** — Platform Admin nav link visible only for super_admin
- Backend: GET /api/admin/platform-stats, full shop/admin CRUD
- 100% test pass on all iterations (11-14)

## Integration Status
| Service | Status |
|---------|--------|
| Stripe Payments | **Active** |
| Google Calendar | **Active** |
| SendGrid Email | **Active** |
| Twilio SMS | Mocked (awaiting credentials) |

## Prioritized Backlog
### P1
- [ ] Celery + Redis migration (replace APScheduler)
- [ ] Billing infrastructure (Stripe Connect)
- [ ] Enable Twilio SMS

### P2
- [ ] MongoDB → PostgreSQL
- [ ] Enhanced multi-shop analytics

## Credentials
- **Super Admin**: admin / admin123
- **Public Booking**: /book or /book/:shopSlug
