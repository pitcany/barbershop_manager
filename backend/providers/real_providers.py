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
import os
import logging

logger = logging.getLogger(__name__)


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
            msg = self.client.messages.create(
                body=message.body,
                from_=message.from_ or self.from_number,
                to=message.to
            )
            
            logger.info(f"[TWILIO] Sent SMS to {message.to}: {msg.sid}")
            
            return SMSResponse(
                success=True,
                message_id=msg.sid
            )
        except Exception as e:
            logger.error(f"[TWILIO] Failed to send SMS: {e}")
            return SMSResponse(success=False, error=str(e))
    
    async def validate_webhook(self, url: str, params: dict, signature: str) -> bool:
        if not self.validator:
            return False
        return self.validator.validate(url, params, signature)


class StripePaymentProvider(PaymentProvider):
    """Real Stripe payment provider using emergentintegrations"""
    
    def __init__(self, webhook_url: str = ""):
        self.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
        self.default_webhook_url = webhook_url
        
        if not self.api_key:
            logger.warning("Stripe API key not found")
    
    def _get_checkout(self, webhook_url: str = "") -> "StripeCheckout":
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        url = webhook_url or self.default_webhook_url
        return StripeCheckout(api_key=self.api_key, webhook_url=url)
    
    async def create_payment_link(
        self,
        amount: float,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str]
    ) -> PaymentLink:
        if not self.api_key:
            raise Exception("Stripe not configured")
        
        try:
            from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest
            
            # Derive webhook_url from success_url's origin
            from urllib.parse import urlparse
            parsed = urlparse(success_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            webhook_url = f"{origin}/api/webhooks/stripe"
            
            checkout = self._get_checkout(webhook_url)
            
            request = CheckoutSessionRequest(
                amount=float(amount),
                currency=currency,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata
            )
            
            response = await checkout.create_checkout_session(request)
            
            logger.info(f"[STRIPE] Created payment session: {response.session_id}")
            
            return PaymentLink(
                url=response.url,
                session_id=response.session_id
            )
        except Exception as e:
            logger.error(f"[STRIPE] Failed to create payment: {e}")
            raise
    
    async def get_payment_status(self, session_id: str) -> PaymentStatus:
        if not self.api_key:
            return PaymentStatus(
                status="unknown",
                payment_status="unknown",
                amount=0,
                currency="usd"
            )
        
        try:
            checkout = self._get_checkout()
            status = await checkout.get_checkout_status(session_id)
            
            return PaymentStatus(
                status=status.status,
                payment_status=status.payment_status,
                amount=status.amount_total / 100,  # Convert from cents
                currency=status.currency,
                metadata=status.metadata
            )
        except Exception as e:
            logger.error(f"[STRIPE] Failed to get payment status: {e}")
            return PaymentStatus(
                status="error",
                payment_status="unknown",
                amount=0,
                currency="usd"
            )
    
    async def handle_webhook(self, request_body: bytes, signature: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"error": "Stripe not configured"}
        
        try:
            checkout = self._get_checkout()
            webhook_response = await checkout.handle_webhook(request_body, signature)
            
            return {
                "event_type": webhook_response.event_type,
                "event_id": webhook_response.event_id,
                "session_id": webhook_response.session_id,
                "payment_status": webhook_response.payment_status,
                "metadata": webhook_response.metadata
            }
        except Exception as e:
            logger.error(f"[STRIPE] Webhook error: {e}")
            return {"error": str(e)}


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
            
            response = self.client.send(mail)
            
            success = response.status_code == 202
            
            logger.info(f"[SENDGRID] Sent email to {message.to}: {response.status_code}")
            
            return EmailResponse(
                success=success,
                message_id=str(response.headers.get("X-Message-Id", ""))
            )
        except Exception as e:
            logger.error(f"[SENDGRID] Failed to send email: {e}")
            return EmailResponse(success=False, error=str(e))


class GoogleCalendarProvider(CalendarProvider):
    """Real Google Calendar provider"""
    
    def __init__(self):
        self.service = None
        self._setup_client()
    
    def _setup_client(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            # Try to load service account credentials
            creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
            if creds_path and os.path.exists(creds_path):
                creds = service_account.Credentials.from_service_account_file(
                    creds_path,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar provider initialized")
            else:
                logger.warning("Google Calendar credentials not found")
        except ImportError:
            logger.warning("Google API libraries not installed")
        except Exception as e:
            logger.error(f"Failed to setup Google Calendar: {e}")
    
    async def create_event(self, calendar_id: str, event: CalendarEvent) -> Optional[str]:
        if not self.service:
            logger.warning("Google Calendar not configured, skipping event creation")
            return None
        
        try:
            event_body = {
                'summary': event.summary,
                'description': event.description,
                'start': {'dateTime': event.start_time.isoformat(), 'timeZone': 'UTC'},
                'end': {'dateTime': event.end_time.isoformat(), 'timeZone': 'UTC'},
            }
            
            if event.attendee_email:
                event_body['attendees'] = [{'email': event.attendee_email}]
            
            result = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            
            logger.info(f"[GCAL] Created event: {result['id']}")
            return result['id']
        except Exception as e:
            logger.error(f"[GCAL] Failed to create event: {e}")
            return None
    
    async def update_event(self, calendar_id: str, event_id: str, event: CalendarEvent) -> bool:
        if not self.service:
            return False
        
        try:
            event_body = {
                'summary': event.summary,
                'description': event.description,
                'start': {'dateTime': event.start_time.isoformat(), 'timeZone': 'UTC'},
                'end': {'dateTime': event.end_time.isoformat(), 'timeZone': 'UTC'},
            }
            
            self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"[GCAL] Failed to update event: {e}")
            return False
    
    async def delete_event(self, calendar_id: str, event_id: str) -> bool:
        if not self.service:
            return False
        
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"[GCAL] Failed to delete event: {e}")
            return False
    
    async def get_availability(
        self, 
        calendar_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarSlot]:
        # For MVP, return empty list if not configured
        if not self.service:
            return []
        
        # TODO: Implement freebusy query
        return []
    
    async def is_slot_available(
        self, 
        calendar_id: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> bool:
        if not self.service:
            return True  # Assume available if not configured
        
        # TODO: Implement availability check
        return True
