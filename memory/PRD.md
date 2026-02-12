# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system must handle inbound SMS, manage booking/rescheduling, enforce deposits/confirmations, fill cancellations from waitlist, and quantify recovered revenue.

## User Choices
- **SMS Integration**: Simulation mode (TWILIO_ENABLED=false) — awaiting user credentials
- **Payments**: Stripe test mode with mock fallback (STRIPE_ENABLED=false)
- **Calendar**: Mock provider (CALENDAR_ENABLED=false)
- **Email**: SendGrid active with user-provided API key
- **Database**: MongoDB (deviation from original PostgreSQL requirement)
- **Authentication**: JWT-based with bcrypt password hashing

## Architecture Overview

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: MongoDB with Motor async driver
- **Authentication**: JWT tokens with bcrypt password hashing (passlib)

### Frontend
- **Framework**: React with Tailwind CSS
- **Components**: Shadcn/UI
- **Charts**: Recharts

### Provider Abstraction Layer
All external services behind interfaces:
- SMSProvider → TwilioSMSProvider or MockSMSProvider
- CalendarProvider → GoogleCalendarProvider or MockCalendarProvider
- EmailProvider → SendGridEmailProvider (ACTIVE) or MockEmailProvider
- PaymentProvider → StripePaymentProvider or MockPaymentProvider

### Agent System
- **FrontDeskAgent**: Handles inbound SMS, booking logic, template responses
- **NoShowEnforcementAgent**: Deposit requests, no-show detection
- **WaitlistFillAgent**: Finds matches and contacts waitlist clients

## What's Been Implemented

### Phase 1: MVP Core (Feb 6, 2026)
- [x] Database models (Shop, Barber, Service, Client, Appointment, Message, Waitlist, Payment, Event)
- [x] Provider abstraction layer with mock/real implementations
- [x] Agent logic (FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent)
- [x] Admin authentication (JWT + bcrypt)
- [x] Dashboard with stats and revenue chart
- [x] Conversations view (SMS message threads)
- [x] Appointments management with status machine
- [x] Waitlist management
- [x] Policy settings editor
- [x] SMS consent form (public page)
- [x] Twilio webhook endpoint
- [x] Stripe webhook endpoint
- [x] Demo data seeding
- [x] SMS compliance (consent tracking, STOP handling)
- [x] Audit logging for all external API calls
- [x] Revenue recovery tracking

### Phase 2: High-Impact Enhancements (Feb 12, 2026)
- [x] **Scheduling Engine**: Conflict prevention, business hours validation, slot availability
- [x] **Client Management Dashboard**: Search, create, view history, book appointments
- [x] **Real-Time Conversations**: Live polling (3s interval), new message indicators
- [x] **Client Detail Page**: Full history (appointments + messages), stats, waitlist management
- [x] **Appointment Booking**: Slot selection from scheduling engine, conflict validation

### All Features Working
- Admin login/logout
- Dashboard statistics & revenue chart
- Client list with search, create, edit
- Client detail with appointment/message history
- Appointment booking with conflict prevention
- Scheduling availability with business hours
- Conversation threads with live polling
- Appointment listing with status filters
- Status updates with state machine validation
- Waitlist management
- Policy settings
- SMS consent form
- SendGrid email integration (active)
- Appointment reminders (manual trigger)

## Mocked Integrations
- **Twilio SMS**: MOCKED (TWILIO_ENABLED=false) — awaiting credentials
- **Stripe Payments**: MOCKED (STRIPE_ENABLED=false)
- **Google Calendar**: MOCKED (CALENDAR_ENABLED=false)

## Prioritized Backlog

### P0 (Completed)
- [x] Core MVP features
- [x] Scheduling Engine with conflict prevention
- [x] Client Management Dashboard
- [x] Real-Time Conversation View

### P1 (Important - Next)
- [ ] Enable Twilio for real SMS (pending user credentials)
- [ ] Implement Background Tasks with Celery for reminders
- [ ] Complete OwnerOpsAgent (daily summary emails via SendGrid)

### P2 (Nice to Have)
- [ ] Build Reporting Dashboard for recovered revenue events
- [ ] RetentionRebookAgent implementation
- [ ] Real Stripe integration for deposits/no-show fees
- [ ] Real Google Calendar integration

### P3 (Future)
- [ ] Migrate from MongoDB to PostgreSQL (as per original requirements)
- [ ] Multi-shop support
- [ ] Client portal for self-service
- [ ] Refactor server.py into modular route files

## Credentials
- **Admin Login**: username=admin, password=admin123
- **Preview URL**: https://waitlist-hero.preview.emergentagent.com
