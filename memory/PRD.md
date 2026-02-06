# Barbershop Autopilot - Product Requirements Document

## Original Problem Statement
Build a production-grade MVP named "barbershop-autopilot" to reduce no-shows and recover lost revenue for a single barbershop. The system must handle inbound SMS, manage booking/rescheduling, enforce deposits/confirmations, fill cancellations from waitlist, and quantify recovered revenue.

## User Choices (From Initial Conversation)
- **SMS Integration**: Simulation mode (TWILIO_ENABLED=false)
- **Payments**: Stripe test mode with mock fallback
- **Calendar**: Mock provider (no Google Calendar credentials)
- **Email**: Mock provider (SEND_EMAILS=false)
- **Database**: MongoDB (available in environment)
- **Authentication**: JWT-based with env-configured admin credentials

## Architecture Overview

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: MongoDB with Motor async driver
- **Authentication**: JWT tokens with bcrypt password hashing

### Frontend
- **Framework**: React with Tailwind CSS
- **Components**: Shadcn/UI
- **Charts**: Recharts

### Provider Abstraction Layer
All external services implemented behind interfaces:
- SMSProvider → TwilioSMSProvider or MockSMSProvider
- CalendarProvider → GoogleCalendarProvider or MockCalendarProvider
- EmailProvider → SendGridEmailProvider or MockEmailProvider
- PaymentProvider → StripePaymentProvider or MockPaymentProvider

### Agent System
- **FrontDeskAgent**: Handles inbound SMS, booking logic, template responses
- **NoShowEnforcementAgent**: Deposit requests, no-show detection
- **WaitlistFillAgent**: Finds matches and contacts waitlist clients

## What's Been Implemented (Feb 6, 2026)

### Phase 1: MVP Core
- [x] Database models (Shop, Barber, Service, Client, Appointment, Message, Waitlist, Payment, Event)
- [x] Provider abstraction layer with mock/real implementations
- [x] Agent logic (FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent)
- [x] Admin authentication (JWT)
- [x] Dashboard with stats and revenue chart
- [x] Conversations view (SMS message threads)
- [x] Appointments management
- [x] Waitlist management
- [x] Policy settings editor
- [x] SMS consent form (public page)
- [x] Twilio webhook endpoint
- [x] Stripe webhook endpoint
- [x] Demo data seeding

### Features Working
- Admin login/logout
- Dashboard statistics (appointments, revenue recovered, no-shows, messages)
- Revenue chart (14-day overview)
- Conversation list and message threads
- Appointment listing with status filters
- Status updates on appointments
- Waitlist view with remove functionality
- Policy settings (deposit amount, timing rules, rate limits)
- SMS consent form submission
- Test SMS sending (when Twilio enabled)

## Core Requirements (Static)

### MVP Agents to Implement
1. **FrontDeskAgent** ✅ - Handle inbound SMS, booking logic
2. **NoShowEnforcementAgent** ✅ - Deposits and no-show tracking
3. **WaitlistFillAgent** ✅ - Fill cancellations from waitlist
4. **RetentionRebookAgent** ⏸️ - Stub only (simple cron)
5. **OwnerOpsAgent** ⏸️ - Stub only (basic summary)

### Business Rules
- No booking outside business hours
- Rate limit: max 4 messages/day/client (unless active conversation)
- Deposits required within 48 hours of appointment
- Clients with previous no-shows require deposits

## Prioritized Backlog

### P0 (Blocking)
- [x] Core MVP features complete

### P1 (Important)
- [ ] Stripe payment link generation for deposits
- [ ] Real Twilio integration testing
- [ ] Appointment reminder scheduling (cron job)

### P2 (Nice to Have)
- [ ] RetentionRebookAgent implementation
- [ ] OwnerOpsAgent with email summaries
- [ ] Multi-barber calendar sync
- [ ] Client portal for self-service

## Next Steps
1. Configure real Twilio credentials and test SMS flow
2. Set up Stripe webhook for payment confirmation
3. Add scheduled job for appointment reminders
4. Consider multi-shop support for future scaling

## User Personas
- **Shop Owner**: Wants to reduce no-shows and track recovered revenue
- **Front Desk Staff**: Needs simple conversation view
- **Clients**: Book/confirm via SMS, provide consent for notifications
