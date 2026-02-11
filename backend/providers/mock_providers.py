"""
Mock providers for local development
"""
from .interfaces import (
    SMSProvider, SMSMessage, SMSResponse,
    CalendarProvider, CalendarEvent, CalendarSlot,
    EmailProvider, EmailMessage, EmailResponse,
    PaymentProvider, PaymentLink, PaymentStatus
)
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class MockSMSProvider(SMSProvider):
    """Mock SMS provider that logs messages instead of sending"""
    
    def __init__(self):
        self.sent_messages: List[Dict] = []
    
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        message_id = f"mock_sms_{uuid.uuid4().hex[:12]}"
        
        msg_data = {
            "id": message_id,
            "to": message.to,
            "body": message.body,
            "from": message.from_,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.sent_messages.append(msg_data)
        
        logger.info(f"[MOCK SMS] To: {message.to} | Message: {message.body[:50]}...")
        
        return SMSResponse(
            success=True,
            message_id=message_id
        )
    
    async def validate_webhook(self, url: str, params: dict, signature: str) -> bool:
        # Mock always validates
        return True


class MockCalendarProvider(CalendarProvider):
    """Mock calendar provider with in-memory event storage"""
    
    def __init__(self):
        self.events: Dict[str, Dict[str, CalendarEvent]] = {}  # calendar_id -> event_id -> event
    
    async def create_event(self, calendar_id: str, event: CalendarEvent) -> Optional[str]:
        if calendar_id not in self.events:
            self.events[calendar_id] = {}
        
        event_id = f"mock_event_{uuid.uuid4().hex[:12]}"
        event.id = event_id
        self.events[calendar_id][event_id] = event
        
        logger.info(f"[MOCK CALENDAR] Created event: {event.summary} at {event.start_time}")
        
        return event_id
    
    async def update_event(self, calendar_id: str, event_id: str, event: CalendarEvent) -> bool:
        if calendar_id in self.events and event_id in self.events[calendar_id]:
            event.id = event_id
            self.events[calendar_id][event_id] = event
            logger.info(f"[MOCK CALENDAR] Updated event: {event_id}")
            return True
        return False
    
    async def delete_event(self, calendar_id: str, event_id: str) -> bool:
        if calendar_id in self.events and event_id in self.events[calendar_id]:
            del self.events[calendar_id][event_id]
            logger.info(f"[MOCK CALENDAR] Deleted event: {event_id}")
            return True
        return False
    
    async def get_availability(
        self, 
        calendar_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarSlot]:
        # Generate mock availability slots (30-minute intervals during business hours)
        slots = []
        current = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        while current < end_date:
            # Skip weekends
            if current.weekday() < 6:  # Mon-Sat
                hour = current.hour
                if 9 <= hour < 18:  # Business hours
                    end_time = current + timedelta(minutes=30)
                    
                    # Check if slot conflicts with existing events
                    available = True
                    if calendar_id in self.events:
                        for event in self.events[calendar_id].values():
                            if (current < event.end_time and end_time > event.start_time):
                                available = False
                                break
                    
                    slots.append(CalendarSlot(
                        start_time=current,
                        end_time=end_time,
                        available=available
                    ))
            
            current += timedelta(minutes=30)
        
        return slots
    
    async def is_slot_available(
        self, 
        calendar_id: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> bool:
        if calendar_id not in self.events:
            return True
        
        for event in self.events[calendar_id].values():
            if (start_time < event.end_time and end_time > event.start_time):
                return False
        
        return True


class MockEmailProvider(EmailProvider):
    """Mock email provider that logs emails to console"""
    
    def __init__(self, db=None, shop_id: str = "demo_shop"):
        self.db = db
        self.shop_id = shop_id
        self.sent_emails: List[Dict] = []
    
    async def send_email(self, message: EmailMessage) -> EmailResponse:
        message_id = f"mock_email_{uuid.uuid4().hex[:12]}"
        
        email_data = {
            "id": message_id,
            "to": message.to,
            "subject": message.subject,
            "from": message.from_email,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.sent_emails.append(email_data)
        
        logger.info(f"[MOCK EMAIL] To: {message.to} | Subject: {message.subject}")
        
        # Store in database if available
        if self.db is not None:
            try:
                await self.db.email_outbox.insert_one({
                    "id": message_id,
                    "shop_id": self.shop_id,
                    "to_email": message.to,
                    "from_email": message.from_email or "noreply@barbershop.local",
                    "subject": message.subject,
                    "html_content": message.html_content,
                    "plain_content": message.plain_content,
                    "sent": False,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to store email in outbox: {e}")
        
        return EmailResponse(
            success=True,
            message_id=message_id
        )


class MockPaymentProvider(PaymentProvider):
    """Mock payment provider for local testing"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
    
    async def create_payment_link(
        self,
        amount: float,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str]
    ) -> PaymentLink:
        session_id = f"mock_session_{uuid.uuid4().hex[:12]}"
        
        self.sessions[session_id] = {
            "amount": amount,
            "currency": currency,
            "status": "open",
            "payment_status": "unpaid",
            "metadata": metadata,
            "success_url": success_url,
            "cancel_url": cancel_url
        }
        
        # In mock mode, return a URL that immediately redirects to success
        mock_url = f"/mock-payment?session_id={session_id}"
        
        logger.info(f"[MOCK PAYMENT] Created session: {session_id} for ${amount}")
        
        return PaymentLink(
            url=mock_url,
            session_id=session_id
        )
    
    async def get_payment_status(self, session_id: str) -> PaymentStatus:
        if session_id not in self.sessions:
            return PaymentStatus(
                status="unknown",
                payment_status="unknown",
                amount=0,
                currency="usd"
            )
        
        session = self.sessions[session_id]
        return PaymentStatus(
            status=session["status"],
            payment_status=session["payment_status"],
            amount=session["amount"],
            currency=session["currency"],
            metadata=session["metadata"]
        )
    
    async def handle_webhook(self, request_body: bytes, signature: str) -> Dict[str, Any]:
        # Mock webhook handler
        return {
            "event_type": "mock.payment",
            "session_id": "mock",
            "payment_status": "paid"
        }
    
    # Helper method for mock payment completion
    async def complete_payment(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = "complete"
            self.sessions[session_id]["payment_status"] = "paid"
            logger.info(f"[MOCK PAYMENT] Completed payment: {session_id}")
