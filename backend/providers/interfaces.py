"""
Provider interfaces for external services
Abstract classes that allow swapping between mock and real implementations
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel


# SMS Provider Interface
class SMSMessage(BaseModel):
    to: str
    body: str
    from_: Optional[str] = None


class SMSResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class SMSProvider(ABC):
    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        """Send an SMS message"""
        pass
    
    @abstractmethod
    async def validate_webhook(self, url: str, params: dict, signature: str) -> bool:
        """Validate incoming webhook signature"""
        pass


# Calendar Provider Interface
class CalendarEvent(BaseModel):
    id: Optional[str] = None
    summary: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendee_email: Optional[str] = None


class CalendarSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool = True


class CalendarProvider(ABC):
    @abstractmethod
    async def create_event(self, calendar_id: str, event: CalendarEvent) -> Optional[str]:
        """Create a calendar event, returns event ID"""
        pass
    
    @abstractmethod
    async def update_event(self, calendar_id: str, event_id: str, event: CalendarEvent) -> bool:
        """Update an existing calendar event"""
        pass
    
    @abstractmethod
    async def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete a calendar event"""
        pass
    
    @abstractmethod
    async def get_availability(
        self, 
        calendar_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarSlot]:
        """Get available time slots for a date range"""
        pass
    
    @abstractmethod
    async def is_slot_available(
        self, 
        calendar_id: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> bool:
        """Check if a specific time slot is available"""
        pass


# Email Provider Interface
class EmailMessage(BaseModel):
    to: str
    subject: str
    html_content: str
    plain_content: Optional[str] = None
    from_email: Optional[str] = None


class EmailResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailProvider(ABC):
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> EmailResponse:
        """Send an email"""
        pass


# Payment Provider Interface
class PaymentLink(BaseModel):
    url: str
    session_id: str


class PaymentStatus(BaseModel):
    status: str
    payment_status: str
    amount: float
    currency: str
    metadata: Dict[str, Any] = {}


class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment_link(
        self,
        amount: float,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str]
    ) -> PaymentLink:
        """Create a payment link for deposits"""
        pass
    
    @abstractmethod
    async def get_payment_status(self, session_id: str) -> PaymentStatus:
        """Get the status of a payment"""
        pass
    
    @abstractmethod
    async def handle_webhook(self, request_body: bytes, signature: str) -> Dict[str, Any]:
        """Handle incoming payment webhook"""
        pass
