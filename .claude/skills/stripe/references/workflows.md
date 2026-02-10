# Stripe Workflows Reference

## Contents
- End-to-End Deposit Collection Flow
- Webhook Processing Workflow
- Mock Payment Testing
- Adding a New Payment Type
- Production Readiness Checklist

---

## End-to-End Deposit Collection Flow

The deposit flow spans three modules: `agents.py` (business logic), `server.py` (routes), and the payment provider.

### Step-by-Step

1. **Client books appointment** — FrontDeskAgent creates appointment with `PENDING` status
2. **Deposit check** — NoShowEnforcementAgent evaluates deposit requirement
3. **Payment link created** — Provider generates checkout URL, payment record saved to MongoDB
4. **Link sent via SMS** — Using the deposit request template
5. **Client pays** — Redirected to success URL or mock auto-completes
6. **Webhook fires** — `POST /api/webhooks/stripe` matches session, updates status
7. **Revenue logged** — `log_no_show_fee_on_payment_success()` hook fires if applicable

```python
# Full flow in NoShowEnforcementAgent.create_deposit_request()
success_url = f"{host_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment_id={appointment_id}"
cancel_url = f"{host_url}/payment/cancel?appointment_id={appointment_id}"

payment_link = await self.payment.create_payment_link(
    amount=amount, currency="usd",
    success_url=success_url, cancel_url=cancel_url,
    metadata={"appointment_id": appointment_id, "client_id": client["id"], "type": "deposit"}
)

# Appointment status: PENDING -> DEPOSIT_PENDING
await self.db.appointments.update_one(
    {"id": appointment_id},
    {"$set": {"deposit_required": True, "deposit_amount": amount,
              "status": AppointmentStatus.DEPOSIT_PENDING.value}}
)

# Payment record created for tracking
await self.db.payments.insert_one({
    "id": str(uuid.uuid4()),
    "stripe_session_id": payment_link.session_id,
    "status": "pending", "payment_type": "deposit", ...
})
```

### SMS Template for Deposits

```python
DEPOSIT_REQUEST = (
    "To secure your appointment, please pay a ${amount} deposit:\n"
    "{payment_link}\n\n"
    "Your appointment will be confirmed once deposit is received."
)
```

---

## Webhook Processing Workflow

The webhook at `POST /api/webhooks/stripe` has no auth — it authenticates via Stripe signature (currently unimplemented in real provider — see WARNING in patterns.md).

```python
# server.py:684-732 — Simplified flow
@api_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    # 1. Delegate to provider
    result = await payment.handle_webhook(body, signature)

    # 2. Error check
    if result.get("error"):
        return JSONResponse(content={"status": "error"}, status_code=400)

    # 3. Match to payment record
    if "session_id" in result:
        payment_record = await db.payments.find_one(
            {"stripe_session_id": result["session_id"]}, {"_id": 0}
        )

        # 4. Update payment + appointment
        if payment_record and result.get("payment_status") == "paid":
            await db.payments.update_one(
                {"stripe_session_id": result["session_id"]},
                {"$set": {"status": "completed", "updated_at": now()}}
            )
            # 5. Revenue attribution hook
            if payment_record.get("appointment_id"):
                appointment = await db.appointments.find_one(...)
                await log_no_show_fee_on_payment_success(db, payment_record, appointment)

    return JSONResponse(content={"status": "received"})
```

### Webhook idempotency

The current implementation does NOT check for duplicate webhook deliveries. For production, add:

```python
# Check if already processed
existing = await db.payments.find_one(
    {"stripe_session_id": session_id, "status": "completed"}, {"_id": 0}
)
if existing:
    return JSONResponse(content={"status": "already_processed"})
```

---

## Mock Payment Testing

In local dev (no `STRIPE_API_KEY`), the `MockPaymentProvider` generates links to `GET /api/mock-payment?session_id=mock_session_xxx` which auto-completes the payment.

```python
# MockPaymentProvider creates links like:
"/mock-payment?session_id=mock_session_abc123def456"

# The mock-payment endpoint auto-completes:
await payment.complete_payment(session_id)  # Sets status=complete, payment_status=paid

# Then updates appointment:
await db.appointments.update_one(
    {"id": appointment_id},
    {"$set": {"deposit_paid": True, "status": AppointmentStatus.DEPOSIT_PAID.value}}
)
```

### Testing with simulate_sms.py

Use the SMS simulator to trigger the deposit flow end-to-end:

```bash
python scripts/simulate_sms.py --mode interactive
# Then send: BOOK
# Follow prompts to create appointment
# If deposit required, mock payment link is returned
```

---

## Adding a New Payment Type

To add a new payment type (e.g., full service payment, cancellation fee):

Copy this checklist and track progress:
- [ ] Step 1: Add payment type string to agent logic (e.g., `"cancellation_fee"`)
- [ ] Step 2: Create payment link with correct metadata type
- [ ] Step 3: Handle in webhook — update payment record status
- [ ] Step 4: Add revenue logging hook if applicable
- [ ] Step 5: Add audit logging via `AuditLogger.log_payment_attempt()`
- [ ] Step 6: Test with mock provider first

```python
# Example: Adding a cancellation fee payment
async def create_cancellation_fee(self, appointment_id: str, client: Dict, fee: float, host_url: str):
    link = await self.payment.create_payment_link(
        amount=fee,
        currency="usd",
        success_url=f"{host_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment_id={appointment_id}",
        cancel_url=f"{host_url}/payment/cancel?appointment_id={appointment_id}",
        metadata={
            "appointment_id": appointment_id,
            "client_id": client["id"],
            "type": "cancellation_fee"  # New type
        }
    )

    await self.db.payments.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": self.shop.id,
        "client_id": client["id"],
        "appointment_id": appointment_id,
        "amount": fee,
        "currency": "usd",
        "stripe_session_id": link.session_id,
        "status": "pending",
        "payment_type": "cancellation_fee",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    return link.url
```

Then update `revenue_logger.py:log_no_show_fee_on_payment_success()` to handle the new type if it should be tracked as recovered revenue.

---

## Production Readiness Checklist

Before enabling real Stripe (`STRIPE_API_KEY` set):

Copy this checklist and track progress:
- [ ] Step 1: Implement webhook signature verification in `StripePaymentProvider.handle_webhook()` using `stripe.Webhook.construct_event()`
- [ ] Step 2: Add `STRIPE_WEBHOOK_SECRET` env var
- [ ] Step 3: Add idempotency check for duplicate webhook deliveries
- [ ] Step 4: Replace `{CHECKOUT_SESSION_ID}` placeholder in success_url — Stripe replaces this automatically
- [ ] Step 5: Set real success/cancel URLs (not localhost)
- [ ] Step 6: Verify `emergentintegrations` package is installed: `pip install emergentintegrations`
- [ ] Step 7: Test with Stripe CLI: `stripe listen --forward-to localhost:8001/api/webhooks/stripe`
- [ ] Step 8: Verify audit logs are recording real Stripe session IDs

Validation loop:
1. Set `STRIPE_API_KEY` to test key (`sk_test_...`)
2. Create a deposit via the agent
3. Verify payment link opens Stripe Checkout
4. Complete payment with test card `4242 4242 4242 4242`
5. Verify webhook fires and updates payment record
6. Check `integration_audit_log` collection for the Stripe entry
7. If any step fails, fix and repeat from step 2

---

## Related Skills

- See the **fastapi** skill for route patterns and the webhook endpoint structure
- See the **mongodb** skill for querying `payments` and `integration_audit_log` collections
- See the **python** skill for async patterns used in provider implementations
