# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system must handle inbound SMS, manage booking/rescheduling, enforce deposits/confirmations, fill cancellations from waitlist, and quantify recovered revenue.

## User Choices
- **SMS Integration**: Simulation mode (TWILIO_ENABLED=false) — awaiting user credentials
- **Payments**: Stripe test mode with mock fallback (STRIPE_ENABLED=false)
- **Calendar**: Mock provider (CALENDAR_ENABLED=false)
- **Email**: SendGrid configured (API key expired — user needs to provide new key)
- **Database**: MongoDB (deviation from original PostgreSQL requirement)
- **Authentication**: JWT-based with bcrypt password hashing
- **Background Tasks**: APScheduler (in-process, no Redis needed)

## Architecture Overview

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: MongoDB with Motor async driver
- **Authentication**: JWT tokens with bcrypt password hashing (passlib)
- **Scheduler**: APScheduler (AsyncIOScheduler) for background tasks

### Frontend
- **Framework**: React with Tailwind CSS
- **Components**: Shadcn/UI
- **Charts**: Recharts

### Provider Abstraction Layer
All external services behind interfaces:
- SMSProvider → TwilioSMSProvider or MockSMSProvider
- CalendarProvider → GoogleCalendarProvider or MockCalendarProvider
- EmailProvider → SendGridEmailProvider or MockEmailProvider
- PaymentProvider → StripePaymentProvider or MockPaymentProvider

### Agent System
- **FrontDeskAgent**: Handles inbound SMS, booking logic, template responses
- **NoShowEnforcementAgent**: Deposit requests, no-show detection
- **WaitlistFillAgent**: Finds matches and contacts waitlist clients
- **OwnerOpsAgent**: Daily summary emails to shop owner

## What's Been Implemented

### Phase 1: MVP Core (Feb 6, 2026)
- [x] Database models and provider abstraction layer
- [x] Agent logic (FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent)
- [x] Admin authentication (JWT + bcrypt)
- [x] Dashboard, Conversations, Appointments, Waitlist, Settings pages
- [x] SMS consent form, Twilio/Stripe webhooks
- [x] SMS compliance, audit logging, revenue recovery tracking

### Phase 2: High-Impact Enhancements (Feb 12, 2026)
- [x] Scheduling Engine with conflict prevention
- [x] Client Management Dashboard (search, create, history)
- [x] Real-Time Conversations with live polling
- [x] Appointment Booking with slot selection

### Phase 3: Background Tasks & OwnerOpsAgent (Feb 12, 2026)
- [x] APScheduler integration (starts on FastAPI startup)
- [x] Automated appointment reminders (hourly)
- [x] OwnerOpsAgent with daily summary email (20:00 UTC)
- [x] Manual trigger endpoints for testing
- [x] Scheduler status endpoint
- [x] Stats compilation: appointments, no-shows, revenue, waitlist, messages, clients

## Background Jobs

| Job | Schedule | Endpoint |
|-----|----------|----------|
| Appointment Reminders | Every hour | POST /api/jobs/reminders/run |
| Daily Summary Email | Daily 20:00 UTC | POST /api/jobs/daily-summary/run |
| Scheduler Status | — | GET /api/jobs/status |

## Mocked Integrations
- **Twilio SMS**: MOCKED (TWILIO_ENABLED=false) — awaiting credentials
- **Stripe Payments**: MOCKED (STRIPE_ENABLED=false)
- **Google Calendar**: MOCKED (CALENDAR_ENABLED=false)
- **SendGrid Email**: Real provider but API key expired (401)

## Prioritized Backlog

### P0 (Completed)
- [x] Core MVP features
- [x] Scheduling Engine with conflict prevention
- [x] Client Management Dashboard
- [x] Real-Time Conversation View
- [x] APScheduler background tasks
- [x] OwnerOpsAgent daily summary emails

### P1 (Important - Next)
- [ ] Enable Twilio for real SMS (pending user credentials)
- [ ] Fix SendGrid API key (expired — user needs to provide new key)
- [ ] Build Reporting Dashboard for recovered revenue events

### P2 (Nice to Have)
- [ ] RetentionRebookAgent implementation
- [ ] Real Stripe integration for deposits/no-show fees
- [ ] Real Google Calendar integration

### P3 (Future)
- [ ] Migrate from MongoDB to PostgreSQL
- [ ] Multi-shop support
- [ ] Client portal for self-service
- [ ] Refactor server.py into modular route files

## Credentials
- **Admin Login**: username=admin, password=admin123
- **Preview URL**: https://waitlist-hero.preview.emergentagent.com
