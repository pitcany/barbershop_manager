# Production Migration Plan: Celery+Redis, Stripe Connect, Twilio Enablement

## Scope and goals
This plan covers three concurrent workstreams:
1. Replace in-process APScheduler with Celery + Redis for production job execution.
2. Migrate deposit billing to Stripe Connect with platform fees.
3. Enable Twilio SMS safely once credentials are available.

The current codebase already has provider abstractions (`backend/providers/*`) and job/business logic modules (`backend/scheduled_jobs.py`, `backend/owner_ops_agent.py`, `backend/retention_rebook_agent.py`), so the migration should preserve those seams and move orchestration/integration code behind new adapters.

## What I found in the current code
- Scheduler is in-process APScheduler started at API startup (`backend/server.py`, `backend/scheduler.py`).
- Job APIs and scheduler status endpoints are APScheduler-centric (`backend/routes/jobs.py`).
- Deposit payment flow is Stripe Checkout via a custom wrapper (`backend/providers/real_providers.py`) and updates both `payment_transactions` + `payments` in multiple places (`backend/routes/payments.py`, `backend/routes/webhooks.py`).
- Twilio provider + webhook signature validation already exist and are gated by env vars (`backend/providers/__init__.py`, `backend/providers/real_providers.py`, `backend/routes/webhooks.py`, `backend/sms_compliance.py`).

## Fault-isolation strategy (cross-cutting)
1. Keep external failures out of request paths.
- API handlers should enqueue work or write state; workers do slow/external IO.
- Webhook handlers should ACK quickly and hand off durable processing.

2. Make all async jobs idempotent.
- Use deterministic idempotency keys per business action (`job_name + shop_id + window`).
- Guard updates with compare-and-set filters (already partially used on payment status updates).

3. Isolate each integration behind a single service boundary.
- Payments: one payment state transition service used by both polling and webhooks.
- SMS: one outbound send path via compliance service.
- Jobs: one task registration module for Celery workers/beat.

4. Add dead-letter + replay paths.
- Failed jobs/events go to a Mongo collection with reason and payload snapshot.
- Admin endpoint for controlled replay by id.

5. Feature-flag every migration.
- `USE_CELERY_SCHEDULER`, `STRIPE_CONNECT_ENABLED`, `TWILIO_ENABLED`.
- Keep fallbacks for staged rollout and rollback.

## Workstream A: Celery + Redis migration (replace APScheduler in production)

### Target architecture
- API process: FastAPI only (no in-process scheduler in production).
- Worker process: Celery worker consuming Redis queue.
- Beat process: Celery beat scheduling periodic tasks.
- Shared task module invokes existing business logic:
  - reminders (`run_reminder_job_for_all_shops`)
  - daily summary (`run_daily_summary_for_all_shops`)
  - retention (`run_retention_for_all_shops`)

### Implementation steps
1. Introduce Celery app and task modules.
- Add `backend/celery_app.py` and `backend/tasks/*.py`.
- Add Redis/Celery config env vars.

2. Port scheduler definitions.
- Convert APScheduler intervals/cron from `backend/scheduler.py` into Celery beat schedule entries.
- Preserve current cadence defaults (`DAILY_SUMMARY_HOUR`, `RETENTION_SWEEP_HOUR`).

3. Replace startup behavior.
- In `backend/server.py`, gate `start_scheduler(db)` behind `USE_CELERY_SCHEDULER=false` (local/dev fallback).
- In production mode, expose status based on worker heartbeat + last run records, not APScheduler internals.

4. Add run tracking and idempotency.
- New collection: `job_runs` with fields like `job_name`, `shop_id`, `window_start`, `window_end`, `status`, `attempt`, `error`, `started_at`, `finished_at`.
- Ensure each periodic task writes run records and skips duplicates.

5. Update jobs endpoints.
- `/api/jobs/status` should return scheduler mode (`celery` vs `apscheduler`) and recent run history.
- `/api/jobs/*/run` endpoints should enqueue tasks and return task IDs.

6. Testing and rollout.
- Unit tests for task wrappers and idempotency guards.
- Integration tests for enqueue -> worker -> DB side effects.
- Production rollout: start workers first, then beat, then flip `USE_CELERY_SCHEDULER`.

### Fault isolation details
- Redis outage: API still serves; job-trigger endpoints fail fast with explicit status; no in-process fallback in production.
- Worker crash: queued tasks persist in Redis; retries controlled by Celery policy.
- Duplicate deliveries: blocked via idempotency key + conditional DB updates.

## Workstream B: Billing infrastructure (Stripe Connect with platform fee on deposits)

### Target architecture
Use Stripe Connect destination charges for deposits:
- Customer pays via Checkout on platform.
- Funds transfer to connected account.
- Platform collects `application_fee_amount`.

### Implementation steps
1. Extend data model/config.
- Add shop-level fields (Mongo + `Shop` model) for Connect:
  - `stripe_connect_account_id`
  - `stripe_charges_enabled`
  - `stripe_payouts_enabled`
  - optional `platform_fee_bps` (or fixed fee policy)
- Add env flag `STRIPE_CONNECT_ENABLED`.

2. Upgrade payment provider interface.
- Extend `PaymentProvider.create_payment_link(...)` to accept connect context and platform fee.
- Implement in `StripePaymentProvider` using Stripe Checkout Session with:
  - `payment_intent_data[application_fee_amount]`
  - `payment_intent_data[transfer_data][destination]`
- Keep mock provider API-compatible.

3. Unify payment state transitions.
- Extract shared logic from `backend/routes/payments.py` and `backend/routes/webhooks.py` into `backend/services/payment_service.py`.
- Single method for state mutation and revenue logging.

4. Webhook hardening.
- Persist `stripe_event_id` and ignore duplicates.
- Acknowledge webhook quickly, process asynchronously when heavy.
- Ensure only verified signatures are processed (already present).

5. Migration/backfill.
- Existing shops without connect account continue on current non-connect path.
- New deposits use connect path only when shop is fully onboarded and `STRIPE_CONNECT_ENABLED=true`.

6. Observability.
- Record fee and transfer IDs in `payment_transactions` metadata.
- Add reconciliation endpoint/report for `gross`, `platform_fee`, `net_to_shop`.

### Fault isolation details
- Stripe API latency/errors during checkout creation: fail only the deposit-link path; appointment remains created with explicit `deposit_error` behavior (already present).
- Webhook retries/duplicates: event-id dedupe prevents double-settlement.
- Partial DB writes: wrap state transitions in ordered, idempotent updates with guards (`payment_status != paid`).

## Workstream C: Enable Twilio SMS (credentials pending)

### Target architecture
- Keep `SMSComplianceService` as the only outbound path.
- Keep provider factory gating (`TWILIO_ENABLED` + creds).
- Enforce webhook signature validation in production.

### Implementation steps
1. Credential readiness checklist.
- Required: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `TWILIO_ENABLED=true`.
- Configure Twilio webhook URL to `/api/webhooks/twilio/inbound`.

2. Preflight validation endpoint.
- Add/extend health diagnostics to confirm provider initialization, from-number validity, and webhook signature mode.

3. Safe cutover.
- Stage 1: keep `TWILIO_ENABLED=false` in production-like env and run end-to-end tests via mock.
- Stage 2: enable Twilio in staging with test numbers.
- Stage 3: production canary for one shop/number, then global rollout.

4. Compliance hardening.
- Ensure STOP keywords and opt-out flow stay enforced (already implemented in `backend/sms_compliance.py`).
- Confirm inbound unknown-number behavior with policy (current code auto-creates client and sets consent true; this should be a documented business decision).

5. Monitoring.
- Track send success/failure rates from `integration_audit_log`.
- Alert on delivery failures and signature verification failures.

### Fault isolation details
- Twilio outage: outbound send fails gracefully; business logic continues with audited failure.
- Invalid webhook signatures: request rejected (403), no state mutation.
- Misconfiguration: provider factory falls back to mock only when explicitly desired; in production, treat missing creds as deployment error.

## Execution order and why
1. Celery + Redis foundation first.
- Reason: it creates durable async processing needed by billing webhooks and SMS retries.

2. Stripe Connect second.
- Reason: higher financial risk; benefits from durable workers, idempotent event processing, and run/event observability.

3. Twilio enablement third (or parallel late stage).
- Reason: plumbing already exists; biggest remaining work is credentials + rollout controls, not architecture.

## Proposed file-level change list
- Scheduling:
  - `backend/server.py`
  - `backend/scheduler.py` (deprecate for production path)
  - `backend/routes/jobs.py`
  - new: `backend/celery_app.py`
  - new: `backend/tasks/reminders.py`, `backend/tasks/owner_ops.py`, `backend/tasks/retention.py`
- Billing:
  - `backend/providers/interfaces.py`
  - `backend/providers/real_providers.py`
  - `backend/providers/mock_providers.py`
  - `backend/routes/payments.py`
  - `backend/routes/webhooks.py`
  - new: `backend/services/payment_service.py`
  - `backend/models.py` (shop connect fields)
- Twilio:
  - `backend/providers/__init__.py`
  - `backend/providers/real_providers.py`
  - `backend/sms_compliance.py`
  - `backend/routes/webhooks.py`
  - `backend/routes/auth.py` (health/test messaging)

## Test plan
1. Unit tests
- Celery task idempotency and retry behavior.
- Stripe Connect session creation params and fee math.
- Twilio signature validation and consent gating.

2. Integration tests
- API enqueue -> worker execution -> DB side effects.
- Stripe webhook duplicate delivery handling.
- End-to-end SMS flow with `TWILIO_ENABLED=false` and `true` (staging).

3. Regression tests to update
- APScheduler-specific tests in `backend/tests/test_scheduler_features.py` and status shape assertions should be updated to scheduler-mode abstraction.

## Rollback plan
- Keep APScheduler code path toggled by env until Celery path is stable.
- Keep non-connect Stripe path as fallback per shop while onboarding Connect accounts.
- Keep Twilio disabled flag as immediate circuit breaker.

## Open decisions needed before implementation
1. Stripe fee model: fixed fee per deposit vs basis points vs hybrid.
2. Stripe account strategy: Express vs Standard accounts for barbershops.
3. Redis topology: managed Redis vs self-hosted.
4. Retry policy defaults: max retries + backoff for SMS and webhook processing.
5. Compliance policy for unknown inbound senders (auto-consent vs pending consent).
