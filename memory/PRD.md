# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system handles inbound SMS, booking/rescheduling, deposits/confirmations, cancellation filling from waitlist, and revenue tracking.

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler
- **Frontend**: React + Tailwind + Shadcn/UI + Recharts
- **Auth**: JWT + bcrypt
- **External Services**: Provider abstraction (real/mock) for Twilio, Stripe, SendGrid, Google Calendar

## Agent System
| Agent | Status | Description |
|-------|--------|-------------|
| FrontDeskAgent | Active | Handles inbound SMS, booking, template responses |
| NoShowEnforcementAgent | Active | Deposit requests, no-show detection |
| WaitlistFillAgent | Active | Finds matches, contacts waitlist clients |
| OwnerOpsAgent | Active | Daily summary emails to shop owner |
| RetentionRebookAgent | Active | Re-engages lapsed clients via email/SMS |

## Background Jobs (APScheduler)
| Job | Schedule | Description |
|-----|----------|-------------|
| Appointment Reminders | Every hour | SMS reminders for upcoming appointments |
| Daily Summary Email | Daily 20:00 UTC | Operational summary to shop owner |
| Client Retention Sweep | Daily 14:00 UTC | Email/SMS outreach to lapsed clients |

## What's Been Implemented

### Phase 1: MVP Core (Feb 6)
- [x] All database models + provider abstraction layer
- [x] Agent system (FrontDesk, NoShow, Waitlist)
- [x] Admin auth, Dashboard, Conversations, Appointments, Waitlist, Settings
- [x] SMS compliance, audit logging, revenue recovery tracking

### Phase 2: High-Impact Enhancements (Feb 12)
- [x] Scheduling Engine with conflict prevention
- [x] Client Management Dashboard (search, create, history, booking)
- [x] Real-Time Conversations with live polling

### Phase 3: Background Tasks & OwnerOpsAgent (Feb 12)
- [x] APScheduler: hourly reminders + daily summary + retention sweep
- [x] OwnerOpsAgent: daily HTML summary email to shop owner

### Phase 4: Dashboards (Feb 12)
- [x] Reporting Dashboard: KPIs, charts, barber performance, recovery events
- [x] Jobs Dashboard: scheduler status, run/preview, execution history

### Phase 5: RetentionRebookAgent (Feb 12)
- [x] Multi-touch escalation: email touch 1 (friendly), touch 2 (warmer), SMS touch 3 (high-signal only)
- [x] Configurable lapse threshold + cooldown period in Settings
- [x] Outreach history tracking + cooldown enforcement
- [x] Scheduled daily sweep at 14:00 UTC

### Phase 6: Stripe & Google Calendar Integrations (Feb 12)
- [x] **Stripe Payments (REAL)**: Checkout sessions via emergentintegrations, payment_transactions collection, status polling, webhook handler
- [x] **Google Calendar (REAL OAuth2)**: OAuth flow (login/callback), token storage/refresh, event CRUD (create on booking, delete on cancel), freebusy availability
- [x] Frontend: Pay Deposit button, Payment Success/Cancel pages, Integrations status in Settings
- [x] Calendar sync: new appointments auto-create Google Calendar events, cancellations auto-delete events

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

### P2 (Future)
- [ ] Client self-service portal (confirm/reschedule via link)
- [ ] Migrate MongoDB to PostgreSQL
- [ ] Refactor server.py into modular route files
- [ ] Multi-shop support

## Key API Endpoints (New)
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/payments/create-deposit/{id} | POST | Create Stripe checkout for appointment deposit |
| /api/payments/status/{session_id} | GET | Poll Stripe payment status |
| /api/payments/transactions | GET | List all payment transactions |
| /api/webhooks/stripe | POST | Stripe webhook handler |
| /api/oauth/calendar/login | GET | Initiate Google Calendar OAuth |
| /api/oauth/calendar/callback | GET | Handle OAuth callback |
| /api/calendar/status | GET | Check calendar connection |
| /api/calendar/disconnect | POST | Disconnect calendar |
| /api/calendar/events | GET | List calendar events |

## Credentials
- **Admin**: username=admin, password=admin123
- **Preview**: https://booking-recovery.preview.emergentagent.com
