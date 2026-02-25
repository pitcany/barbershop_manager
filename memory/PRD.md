# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade multi-shop SaaS platform named "barbershop-autopilot" to reduce no-shows and recover lost revenue for barbershops.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt (super_admin + shop_admin roles)
- **Multi-tenancy**: Every model has shop_id, unique slug index

### Code Structure
```
/app/backend/
  server.py, deps.py, models.py, demo_seed.py
  routes/ (admin.py, auth.py, appointments.py, clients.py, payments.py, calendar.py, jobs.py, public.py, webhooks.py)
  providers/, agents/, scheduler.py
/app/frontend/src/
  pages/ (SuperAdminPage, DashboardPage, AppointmentsPage, ManagePage, SettingsPage, ClientsPage, BookingPage, ConversationsPage, ReportingPage, etc.)
```

## Completed Features (all tested)

### Core MVP (Phases 1-8)
- Agent system, scheduling, client management, waitlist
- Stripe (REAL), Google Calendar (REAL OAuth2), SendGrid (REAL)
- Client booking portal at /book/:shopSlug, modular backend

### Manager Workflow (Phase 9-10)
- New Appointment, Barber/Service CRUD, Today's Schedule, editable shop details, booking link

### Multi-Shop Platform (Phase 11-12)
- Platform Admin with aggregate stats + per-shop performance
- Shop/Admin CRUD, role-based UI

### Demo Mode & Bug Fixes (Feb 25, 2026) — LATEST
- **Demo Mode Toggle** in Platform Admin — "Seed Demo Data" and "Clear Data" buttons per shop
- **Realistic demo data**: 15 clients, 4 barbers, 7 services, 150+ appointments, 40+ messages (10 realistic SMS threads), 90+ transactions, 12 recovery events, 5 waitlist entries
- **Fixed**: Conversation polling phantom counter (initialized lastPollTime to now)
- **Fixed**: Conversation field name mismatch (content vs body, client_name vs client.name)
- **Fixed**: Recovered revenue missing from reporting (added attributed_at/source to seed)

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
