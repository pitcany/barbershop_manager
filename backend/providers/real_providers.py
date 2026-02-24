"""
Real providers using Twilio, Stripe, SendGrid, Google Calendar
"""
from .interfaces import (
    SMSProvider, SMSMessage, SMSResponse,
    CalendarProvider, CalendarEvent, CalendarSlot,
    EmailProvider, EmailMessage, EmailResponse,
    PaymentProvider, PaymentLink, PaymentStatus
)
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT = 30  # seconds for external API calls


class TwilioSMSProvider(SMSProvider):
    """Real Twilio SMS provider"""
    
    def __init__(self):
        try:
            from twilio.rest import Client
            from twilio.request_validator import RequestValidator
            
            self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            self.from_number = os.environ.get("TWILIO_PHONE_NUMBER")
            
            if self.account_sid and self.auth_token:
                self.client = Client(self.account_sid, self.auth_token)
                self.validator = RequestValidator(self.auth_token)
                logger.info("Twilio SMS provider initialized")
            else:
                self.client = None
                self.validator = None
                logger.warning("Twilio credentials not found")
        except ImportError:
            self.client = None
            self.validator = None
            logger.warning("Twilio library not installed")
    
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        if not self.client:
            return SMSResponse(success=False, error="Twilio not configured")

        try:
            msg = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.messages.create,
                    body=message.body,
                    from_=message.from_ or self.from_number,
                    to=message.to
                ),
                timeout=PROVIDER_TIMEOUT
            )

            logger.info(f"[TWILIO] Sent SMS to {message.to}: {msg.sid}")

            return SMSResponse(
                success=True,
                message_id=msg.sid
            )
        except asyncio.TimeoutError:
            logger.error(f"[TWILIO] Timeout sending SMS to {message.to}")
            return SMSResponse(success=False, error="Twilio request timed out")
        except Exception as e:
            logger.error(f"[TWILIO] Failed to send SMS: {e}")
            return SMSResponse(success=False, error=str(e))
    
    async def validate_webhook(self, url: str, params: dict, signature: str) -> bool:
        if not self.validator:
            return False
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.validator.validate, url, params, signature),
                timeout=PROVIDER_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("[TWILIO] Timeout validating webhook signature")
            return False


class StripePaymentProvider(PaymentProvider):
    """Real Stripe payment provider using Stripe SDK."""

    def __init__(self, webhook_url: str = ""):
        self.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
        self.webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        self.default_webhook_url = webhook_url

        if not self.api_key:
            logger.warning("Stripe API key not found")
    
    def _is_connect_enabled(self) -> bool:
        return os.environ.get("STRIPE_CONNECT_ENABLED", "false").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )
    
    async def create_payment_link(
        self,
        amount: float,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str],
        connect_account_id: Optional[str] = None,
        application_fee_amount: Optional[int] = None,
    ) -> PaymentLink:
        if not self.api_key:
            raise Exception("Stripe not configured")

        try:
            import stripe

            stripe.api_key = self.api_key
            unit_amount = max(1, int(round(float(amount) * 100)))
            pi_data: Dict[str, Any] = {"metadata": metadata}

            if self._is_connect_enabled() and connect_account_id:
                pi_data["transfer_data"] = {"destination": connect_account_id}
                if application_fee_amount and application_fee_amount > 0:
                    pi_data["application_fee_amount"] = int(application_fee_amount)

            session = await asyncio.wait_for(
                asyncio.to_thread(
                    stripe.checkout.Session.create,
                    mode="payment",
                    line_items=[
                        {
                            "price_data": {
                                "currency": currency.lower(),
                                "product_data": {"name": "Barbershop Deposit"},
                                "unit_amount": unit_amount,
                            },
                            "quantity": 1,
                        }
                    ],
                    payment_intent_data=pi_data,
                    metadata=metadata,
                    success_url=success_url,
                    cancel_url=cancel_url,
                ),
                timeout=PROVIDER_TIMEOUT,
            )

            logger.info(f"[STRIPE] Created payment session: {session.id}")

            return PaymentLink(
                url=session.url,
                session_id=session.id,
            )
        except asyncio.TimeoutError:
            logger.error("[STRIPE] Timeout creating payment session")
            raise
        except Exception as e:
            logger.error(f"[STRIPE] Failed to create payment: {e}")
            raise

    async def get_payment_status(self, session_id: str) -> PaymentStatus:
        if not self.api_key:
            return PaymentStatus(
                status="unknown",
                payment_status="unknown",
                amount=0,
                currency="usd",
            )

        try:
            import stripe

            stripe.api_key = self.api_key
            session = await asyncio.wait_for(
                asyncio.to_thread(
                    stripe.checkout.Session.retrieve,
                    session_id,
                    expand=["payment_intent"],
                ),
                timeout=PROVIDER_TIMEOUT,
            )

            payment_intent = session.get("payment_intent")
            metadata = dict(session.get("metadata") or {})
            pi_id = None
            destination_account_id = None
            application_fee_amount = None

            if isinstance(payment_intent, dict):
                pi_id = payment_intent.get("id")
                transfer_data = payment_intent.get("transfer_data") or {}
                destination_account_id = transfer_data.get("destination")
                application_fee_amount = payment_intent.get("application_fee_amount")
            elif isinstance(payment_intent, str):
                pi_id = payment_intent

            if pi_id:
                metadata["payment_intent_id"] = pi_id
            if destination_account_id:
                metadata["destination_account_id"] = destination_account_id
            if application_fee_amount is not None:
                metadata["application_fee_amount"] = application_fee_amount

            return PaymentStatus(
                status=session.get("status", "unknown"),
                payment_status=session.get("payment_status", "unknown"),
                amount=(session.get("amount_total") or 0) / 100,
                currency=session.get("currency", "usd"),
                metadata=metadata,
            )
        except asyncio.TimeoutError:
            logger.error("[STRIPE] Timeout getting payment status")
            return PaymentStatus(
                status="error",
                payment_status="unknown",
                amount=0,
                currency="usd",
            )
        except Exception as e:
            logger.error(f"[STRIPE] Failed to get payment status: {e}")
            return PaymentStatus(
                status="error",
                payment_status="unknown",
                amount=0,
                currency="usd",
            )

    async def handle_webhook(self, request_body: bytes, signature: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"error": "Stripe not configured"}

        if not self.webhook_secret:
            logger.error("[STRIPE] STRIPE_WEBHOOK_SECRET not configured — rejecting webhook")
            return {"error": "Webhook secret not configured"}

        try:
            import stripe

            stripe.api_key = self.api_key
            event = stripe.Webhook.construct_event(
                request_body,
                signature,
                self.webhook_secret,
            )
        except stripe.error.SignatureVerificationError:
            logger.warning("[STRIPE] Webhook signature verification failed")
            return {"error": "Invalid signature"}
        except Exception as e:
            logger.error(f"[STRIPE] Webhook parse error: {e}")
            return {"error": "Webhook verification failed"}

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            payment_intent = session.get("payment_intent")
            payment_intent_id = None
            destination_account_id = None
            application_fee_amount = None

            if payment_intent:
                try:
                    pi = await asyncio.wait_for(
                        asyncio.to_thread(
                            stripe.PaymentIntent.retrieve,
                            payment_intent,
                        ),
                        timeout=PROVIDER_TIMEOUT,
                    )
                    payment_intent_id = pi.get("id")
                    application_fee_amount = pi.get("application_fee_amount")
                    transfer_data = pi.get("transfer_data") or {}
                    destination_account_id = transfer_data.get("destination")
                except Exception as e:
                    logger.warning(
                        "[STRIPE] Failed to expand PaymentIntent for session %s: %s",
                        session.get("id"),
                        e,
                    )

            return {
                "event_id": event.get("id"),
                "event_type": event["type"],
                "session_id": session.get("id"),
                "payment_status": session.get("payment_status"),
                "payment_intent_id": payment_intent_id or payment_intent,
                "destination_account_id": destination_account_id,
                "application_fee_amount": application_fee_amount,
                "currency": session.get("currency"),
                "amount_total": session.get("amount_total"),
            }

        if event["type"] == "checkout.session.expired":
            session = event["data"]["object"]
            return {
                "event_id": event.get("id"),
                "event_type": event["type"],
                "session_id": session.get("id"),
                "payment_status": session.get("payment_status", "unpaid"),
                "checkout_status": "expired",
            }

        return {
            "event_id": event.get("id"),
            "event_type": event["type"],
            "status": "acknowledged",
        }


class SendGridEmailProvider(EmailProvider):
    """Real SendGrid email provider"""
    
    def __init__(self):
        self.api_key = os.environ.get("SENDGRID_API_KEY")
        self.sender_email = os.environ.get("SENDER_EMAIL", "noreply@barbershop-autopilot.com")
        self.client = None
        
        if self.api_key:
            try:
                from sendgrid import SendGridAPIClient
                self.client = SendGridAPIClient(self.api_key)
                logger.info("SendGrid email provider initialized")
            except ImportError:
                logger.warning("SendGrid library not installed")
        else:
            logger.warning("SendGrid API key not found")
    
    async def send_email(self, message: EmailMessage) -> EmailResponse:
        if not self.client:
            return EmailResponse(success=False, error="SendGrid not configured")

        try:
            from sendgrid.helpers.mail import Mail

            mail = Mail(
                from_email=message.from_email or self.sender_email,
                to_emails=message.to,
                subject=message.subject,
                html_content=message.html_content,
                plain_text_content=message.plain_content
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(self.client.send, mail),
                timeout=PROVIDER_TIMEOUT
            )

            success = response.status_code == 202

            logger.info(f"[SENDGRID] Sent email to {message.to}: {response.status_code}")

            return EmailResponse(
                success=success,
                message_id=str(response.headers.get("X-Message-Id", ""))
            )
        except asyncio.TimeoutError:
            logger.error(f"[SENDGRID] Timeout sending email to {message.to}")
            return EmailResponse(success=False, error="SendGrid request timed out")
        except Exception as e:
            logger.error(f"[SENDGRID] Failed to send email: {e}")
            return EmailResponse(success=False, error=str(e))


class GoogleCalendarProvider(CalendarProvider):
    """Real Google Calendar provider using OAuth2"""
    
    def __init__(self, db=None):
        self.db = db
        self.client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        
        if self.client_id and self.client_secret:
            logger.info("Google Calendar provider initialized (OAuth2)")
        else:
            logger.warning("Google Calendar OAuth credentials not found")
    
    async def _get_service(self):
        """Get an authenticated Google Calendar service using stored OAuth tokens"""
        if self.db is None or not self.client_id:
            return None
        
        tokens_doc = await self.db.google_calendar_tokens.find_one({}, {"_id": 0})
        if not tokens_doc or not tokens_doc.get("access_token"):
            logger.warning("No Google Calendar tokens found - user needs to connect")
            return None
        
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from googleapiclient.discovery import build
        
        creds = Credentials(
            token=tokens_doc["access_token"],
            refresh_token=tokens_doc.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            await self.db.google_calendar_tokens.update_one(
                {},
                {"$set": {"access_token": creds.token}},
                upsert=True
            )
        
        return build("calendar", "v3", credentials=creds)
    
    async def create_event(self, calendar_id: str, event: CalendarEvent) -> Optional[str]:
        service = await self._get_service()
        if not service:
            logger.warning("Google Calendar not connected, skipping event creation")
            return None
        
        try:
            event_body = {
                "summary": event.summary,
                "description": event.description or "",
                "start": {"dateTime": event.start_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": event.end_time.isoformat(), "timeZone": "UTC"},
            }
            if event.location:
                event_body["location"] = event.location
            if event.attendee_email:
                event_body["attendees"] = [{"email": event.attendee_email}]

            result = await asyncio.wait_for(
                asyncio.to_thread(
                    service.events().insert(calendarId=calendar_id, body=event_body).execute
                ),
                timeout=PROVIDER_TIMEOUT
            )

            logger.info(f"[GCAL] Created event: {result['id']}")
            return result["id"]
        except asyncio.TimeoutError:
            logger.error("[GCAL] Timeout creating calendar event")
            return None
        except Exception as e:
            logger.error(f"[GCAL] Failed to create event: {e}")
            return None
    
    async def update_event(self, calendar_id: str, event_id: str, event: CalendarEvent) -> bool:
        service = await self._get_service()
        if not service:
            return False
        
        try:
            event_body = {
                "summary": event.summary,
                "description": event.description or "",
                "start": {"dateTime": event.start_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": event.end_time.isoformat(), "timeZone": "UTC"},
            }
            await asyncio.wait_for(
                asyncio.to_thread(
                    service.events().update(calendarId=calendar_id, eventId=event_id, body=event_body).execute
                ),
                timeout=PROVIDER_TIMEOUT
            )
            logger.info(f"[GCAL] Updated event: {event_id}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"[GCAL] Timeout updating event: {event_id}")
            return False
        except Exception as e:
            logger.error(f"[GCAL] Failed to update event: {e}")
            return False
    
    async def delete_event(self, calendar_id: str, event_id: str) -> bool:
        service = await self._get_service()
        if not service:
            return False
        
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    service.events().delete(calendarId=calendar_id, eventId=event_id).execute
                ),
                timeout=PROVIDER_TIMEOUT
            )
            logger.info(f"[GCAL] Deleted event: {event_id}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"[GCAL] Timeout deleting event: {event_id}")
            return False
        except Exception as e:
            logger.error(f"[GCAL] Failed to delete event: {e}")
            return False
    
    async def get_availability(
        self, 
        calendar_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarSlot]:
        service = await self._get_service()
        if not service:
            return []
        
        try:
            body = {
                "timeMin": start_date.isoformat(),
                "timeMax": end_date.isoformat(),
                "items": [{"id": calendar_id}]
            }
            result = await asyncio.wait_for(
                asyncio.to_thread(service.freebusy().query(body=body).execute),
                timeout=PROVIDER_TIMEOUT
            )
            busy_slots = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])

            # Generate 30-min slots for business hours, mark busy ones
            slots = []
            current = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
            while current < end_date:
                if current.weekday() < 6 and 9 <= current.hour < 18:
                    end_time = current + timedelta(minutes=30)
                    available = True
                    for busy in busy_slots:
                        busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
                        busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
                        if current < busy_end and end_time > busy_start:
                            available = False
                            break
                    slots.append(CalendarSlot(start_time=current, end_time=end_time, available=available))
                current += timedelta(minutes=30)
            return slots
        except asyncio.TimeoutError:
            logger.error("[GCAL] Timeout getting availability")
            return []
        except Exception as e:
            logger.error(f"[GCAL] Failed to get availability: {e}")
            return []
    
    async def is_slot_available(
        self, 
        calendar_id: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> bool:
        service = await self._get_service()
        if not service:
            return True  # Assume available if not configured
        
        try:
            body = {
                "timeMin": start_time.isoformat(),
                "timeMax": end_time.isoformat(),
                "items": [{"id": calendar_id}]
            }
            result = await asyncio.wait_for(
                asyncio.to_thread(service.freebusy().query(body=body).execute),
                timeout=PROVIDER_TIMEOUT
            )
            busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
            return len(busy) == 0
        except asyncio.TimeoutError:
            logger.error("[GCAL] Timeout checking slot availability")
            return True
        except Exception as e:
            logger.error(f"[GCAL] Failed to check availability: {e}")
            return True
