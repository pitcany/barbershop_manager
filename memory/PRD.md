# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system handles inbound SMS, booking/rescheduling, deposits/confirmations, cancellation filling from waitlist, and revenue tracking.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt
- **External Services**: Provider abstraction (real/mock) for Twilio, Stripe, SendGrid, Google Calendar

## What's Been Implemented

### Phase 1: MVP Core (Feb 6)
- [x] All database models + provider abstraction layer
- [x] Agent system (FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent)
- [x] Admin auth, Dashboard, Conversations, Appointments, Waitlist, Settings
- [x] SMS compliance, audit logging, revenue recovery tracking
- [x] SendGrid email integration, Twilio/Stripe webhooks

### Phase 2: High-Impact Enhancements (Feb 12)
- [x] Scheduling Engine with conflict prevention
- [x] Client Management Dashboard (search, create, history)
- [x] Real-Time Conversations with live polling
- [x] Client Detail page with appointment booking

### Phase 3: Background Tasks & OwnerOpsAgent (Feb 12)
- [x] APScheduler: hourly reminders + daily 20:00 UTC summary
- [x] OwnerOpsAgent: compiles stats, sends HTML email to shop owner
- [x] Manual trigger + preview endpoints for both jobs

### Phase 4: Dashboards (Feb 12)
- [x] Reporting Dashboard: KPI cards, appointment trend chart, status pie, revenue line, barber performance, message activity, recovery events, period selector
- [x] Jobs Dashboard: scheduler status, job cards with Run Now/Preview, execution history

## Mocked Integrations
- Twilio SMS (TWILIO_ENABLED=false) — awaiting credentials
- Stripe Payments (STRIPE_ENABLED=false)
- Google Calendar (CALENDAR_ENABLED=false)
- SendGrid: real provider, trial expired (401)

## Prioritized Backlog

### P1 (Next)
- [ ] Enable Twilio for real SMS (pending credentials)
- [ ] Fix SendGrid (trial expired — user to upgrade plan)
- [ ] RetentionRebookAgent implementation

### P2 (Nice to Have)
- [ ] Real Stripe integration for deposits/no-show fees
- [ ] Real Google Calendar integration

### P3 (Future)
- [ ] Migrate MongoDB to PostgreSQL
- [ ] Refactor server.py into modular route files
- [ ] Multi-shop support, client portal

## Credentials
- **Admin**: username=admin, password=admin123
- **Preview**: https://waitlist-hero.preview.emergentagent.com
- **Shop owner email**: yannik@pitcananalytics.com
