# Barbershop Autopilot MVP

A production-grade MVP system to reduce no-shows and recover lost revenue for barbershops.

## Features

- **SMS Appointment Management**: Handle inbound SMS for booking, confirming, and cancelling appointments
- **Deposit Enforcement**: Require deposits for last-minute bookings or repeat no-shows
- **Waitlist Filling**: Automatically contact waitlist clients when slots open up
- **Revenue Tracking**: Dashboard showing recovered revenue and no-show metrics
- **Admin Dashboard**: View conversations, manage appointments, and configure policies

## SMS Compliance & Safety

This system is designed for **one real barbershop MVP** and includes compliance safeguards:

### Opt-In Requirements
- **Explicit Consent Tracking**: All clients must have `sms_consent = true` before receiving any outbound SMS
- **Consent Source Recorded**: Tracks how consent was obtained (`web_form`, `inbound_sms`, `manual`)
- **Timestamp Tracking**: Records when consent was granted

### STOP/Opt-Out Handling
When a client texts `STOP`, `UNSUBSCRIBE`, or `CANCEL` (case-insensitive):
1. Their consent is immediately revoked (`sms_consent = false`)
2. One confirmation message is sent: *"You have been unsubscribed and will no longer receive messages."*
3. All future outbound SMS to that client is suppressed

### Provider Toggles (Environment Flags)
All external integrations are gated behind environment flags (default: `false`):

| Flag | Description |
|------|-------------|
| `TWILIO_ENABLED` | Enable/disable real SMS sending |
| `STRIPE_ENABLED` | Enable/disable real payment processing |
| `SEND_EMAILS` | Enable/disable real email sending (SendGrid) |
| `CALENDAR_ENABLED` | Enable/disable Google Calendar integration |

When disabled:
- No external API calls are made
- Business logic still executes
- All attempts are recorded in the audit log

### Integration Audit Log
All external side effects are logged to `integration_audit_log`:
- SMS sends (success or blocked)
- Payment attempts
- Calendar mutations
- Email sends

View the audit log via: `GET /api/audit-log`

### Local Safety Guarantees
The system can run locally via docker-compose with:
- No API keys required
- No outbound network calls
- Deterministic behavior

## Quick Start

### Prerequisites

- Docker and Docker Compose (for containerized setup)
- OR Node.js 18+ and Python 3.11+ (for local development)

### Local Development

1. **Backend Setup**:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8001
```

2. **Frontend Setup**:
```bash
cd frontend
yarn install
yarn start
```

3. **Access the Application**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001/api
- Admin Login: `admin` / `admin123`

## SMS Simulation (No Twilio Required)

Test the SMS flow without live Twilio credentials:

```bash
# Demo conversation
python scripts/simulate_sms.py --mode demo

# Interactive mode
python scripts/simulate_sms.py --mode interactive

# Test all commands
python scripts/simulate_sms.py --mode test
```

## Configuration

### Environment Variables

**Backend (.env)**:
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=barbershop_autopilot
JWT_SECRET=your-secret-key
ADMIN_PASSWORD=admin123

# SMS (disabled by default)
TWILIO_ENABLED=false
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890

# Email (disabled by default)
SEND_EMAILS=false
SENDGRID_API_KEY=your-key
SENDER_EMAIL=noreply@yourdomain.com

# Payments
STRIPE_API_KEY=sk_test_...
```

### Enabling Twilio (Production)

1. Set `TWILIO_ENABLED=true`
2. Add your Twilio credentials
3. Configure your Twilio number to send webhooks to:
   `https://your-domain.com/api/webhooks/twilio/inbound`

### Enabling Stripe (Production)

1. Replace test key with live key: `STRIPE_API_KEY=sk_live_...`
2. Configure webhook endpoint: `https://your-domain.com/api/webhooks/stripe`

## API Endpoints

### Public
- `POST /api/public/sms-consent` - SMS consent form
- `GET /api/public/shop-info` - Shop information

### Webhooks
- `POST /api/webhooks/twilio/inbound` - Twilio SMS webhook
- `POST /api/webhooks/stripe` - Stripe payment webhook

### Admin (Authenticated)
- `POST /api/auth/login` - Admin login
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/dashboard/revenue-chart` - Revenue chart data
- `GET /api/appointments` - List appointments
- `GET /api/conversations` - List SMS conversations
- `GET /api/waitlist` - List waitlist entries
- `PATCH /api/shop/policy` - Update shop policies
- `POST /api/sms/send-test` - Send test SMS (requires TWILIO_ENABLED=true)

## Architecture

### Provider Abstraction

All external services use provider interfaces for easy mocking:

- **SMSProvider**: Twilio (real) or MockSMSProvider
- **CalendarProvider**: Google Calendar or MockCalendarProvider  
- **EmailProvider**: SendGrid or MockEmailProvider
- **PaymentProvider**: Stripe or MockPaymentProvider

### Agent System

- **FrontDeskAgent**: Handles inbound SMS, booking logic
- **NoShowEnforcementAgent**: Manages deposits and no-show detection
- **WaitlistFillAgent**: Fills cancelled slots from waitlist

## Demo Data

The system seeds with demo data on first run:

- **Shop**: Classic Cuts Barbershop
- **Barbers**: Marcus Johnson, David Lee, Anthony Davis
- **Services**: Classic Haircut ($25), Haircut + Beard ($35), Premium Cut ($50), Kids Cut ($15)
- **Sample Clients**: John Smith, Mike Wilson, James Brown
- **Sample Appointments & Conversations**

## Tech Stack

- **Backend**: FastAPI, MongoDB, Python 3.11+
- **Frontend**: React, Tailwind CSS, Shadcn/UI
- **Payments**: Stripe (via emergentintegrations)
- **SMS**: Twilio (optional)
- **Email**: SendGrid (optional)

## Support

For questions or issues, check the logs:
```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log

# Frontend logs
tail -f /var/log/supervisor/frontend.out.log
```

## License

Proprietary - All rights reserved.
