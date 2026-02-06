"""
Database models for Barbershop Autopilot MVP
Using MongoDB with Motor async driver
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, timezone, time
from enum import Enum
import uuid


def generate_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Enums
class AppointmentStatus(str, Enum):
    PENDING = "pending"  # Created, awaiting confirmation
    CONFIRMED = "confirmed"  # Client confirmed
    DEPOSIT_PENDING = "deposit_pending"  # Waiting for deposit
    DEPOSIT_PAID = "deposit_paid"  # Deposit received
    COMPLETED = "completed"  # Service delivered
    NO_SHOW = "no_show"  # Client didn't show up
    CANCELLED = "cancelled"  # Cancelled by client/shop
    RESCHEDULED = "rescheduled"  # Moved to new time


class MessageDirection(str, Enum):
    INBOUND = "inbound"  # From client
    OUTBOUND = "outbound"  # To client


class MessageType(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    SYSTEM = "system"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class EventType(str, Enum):
    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    DEPOSIT_PAID = "deposit_paid"
    NO_SHOW_DETECTED = "no_show_detected"
    WAITLIST_FILLED = "waitlist_filled"
    SMS_SENT = "sms_sent"
    SMS_RECEIVED = "sms_received"
    REVENUE_RECOVERED = "revenue_recovered"


# Base Models
class Shop(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    name: str
    phone: str  # Shop's Twilio number
    email: Optional[str] = None
    address: Optional[str] = None
    timezone: str = "America/New_York"
    
    # Business hours (stored as JSON)
    business_hours: dict = Field(default_factory=lambda: {
        "monday": {"open": "09:00", "close": "18:00"},
        "tuesday": {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "thursday": {"open": "09:00", "close": "18:00"},
        "friday": {"open": "09:00", "close": "18:00"},
        "saturday": {"open": "09:00", "close": "17:00"},
        "sunday": None  # Closed
    })
    
    # Policies
    deposit_amount: float = 20.0  # Default deposit
    deposit_required_hours: int = 48  # Require deposit if booking within X hours
    confirmation_window_hours: int = 24  # Hours before appointment to send confirmation
    cancellation_window_hours: int = 4  # Minimum notice for cancellation
    max_messages_per_day: int = 4  # Rate limit for outbound SMS
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Barber(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    active: bool = True
    calendar_id: Optional[str] = None  # Google Calendar ID
    
    created_at: datetime = Field(default_factory=utc_now)


class Service(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    name: str
    description: Optional[str] = None
    duration_minutes: int = 30
    price: float
    active: bool = True
    
    created_at: datetime = Field(default_factory=utc_now)


class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    name: str
    phone: str  # Primary identifier for SMS
    email: Optional[str] = None
    
    # SMS consent (compliance required)
    sms_consent: bool = False
    sms_consent_timestamp: Optional[datetime] = None
    sms_consent_source: Optional[str] = None  # e.g., "web_form", "inbound_sms", "manual"
    
    # Stripe customer
    stripe_customer_id: Optional[str] = None
    
    # Stats
    total_appointments: int = 0
    no_shows: int = 0
    last_visit: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Appointment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    client_id: str
    barber_id: str
    service_id: str
    
    # Scheduling
    scheduled_at: datetime
    duration_minutes: int
    
    # Status tracking
    status: AppointmentStatus = AppointmentStatus.PENDING
    confirmed_at: Optional[datetime] = None
    
    # Deposit tracking
    deposit_required: bool = False
    deposit_amount: float = 0.0
    deposit_paid: bool = False
    deposit_payment_id: Optional[str] = None
    
    # Google Calendar
    calendar_event_id: Optional[str] = None
    
    # Notes
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    client_id: str
    
    direction: MessageDirection
    message_type: MessageType = MessageType.SMS
    
    content: str
    
    # Twilio tracking
    twilio_sid: Optional[str] = None
    twilio_status: Optional[str] = None
    
    # Context
    appointment_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=utc_now)


class Waitlist(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    client_id: str
    barber_id: Optional[str] = None  # Preferred barber (optional)
    service_id: str
    
    # Availability
    preferred_date: datetime
    flexible_hours: int = 2  # +/- hours they're flexible
    
    # Status
    active: bool = True
    filled_appointment_id: Optional[str] = None
    
    # Contact attempts
    contact_attempts: int = 0
    last_contacted: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=utc_now)


class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    client_id: str
    appointment_id: Optional[str] = None
    
    amount: float
    currency: str = "usd"
    
    # Stripe tracking
    stripe_session_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    
    status: PaymentStatus = PaymentStatus.PENDING
    
    # Metadata
    payment_type: str = "deposit"  # deposit, full_payment, no_show_fee
    description: Optional[str] = None
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    event_type: EventType
    
    # References
    client_id: Optional[str] = None
    appointment_id: Optional[str] = None
    payment_id: Optional[str] = None
    
    # Data
    data: dict = Field(default_factory=dict)
    
    # Revenue tracking
    revenue_impact: float = 0.0  # Positive = recovered, negative = lost
    
    created_at: datetime = Field(default_factory=utc_now)


class EmailOutbox(BaseModel):
    """Stores emails when SEND_EMAILS=false for inspection"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    
    to_email: str
    from_email: str
    subject: str
    html_content: str
    plain_content: Optional[str] = None
    
    sent: bool = False
    sent_at: Optional[datetime] = None
    error: Optional[str] = None
    
    created_at: datetime = Field(default_factory=utc_now)


# Admin User
class AdminUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    username: str
    password_hash: str
    
    created_at: datetime = Field(default_factory=utc_now)
    last_login: Optional[datetime] = None


# Request/Response Models
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SMSConsentRequest(BaseModel):
    phone: str
    name: str
    consent: bool


class PolicyUpdate(BaseModel):
    deposit_amount: Optional[float] = None
    deposit_required_hours: Optional[int] = None
    confirmation_window_hours: Optional[int] = None
    cancellation_window_hours: Optional[int] = None
    max_messages_per_day: Optional[int] = None
    business_hours: Optional[dict] = None


class SendTestSMSRequest(BaseModel):
    to_phone: str
    message: str


class SendTestEmailRequest(BaseModel):
    to_email: str
    subject: str = "Test Email from Barbershop Autopilot"
    message: str = "This is a test email to verify SendGrid integration is working correctly."


# Integration Audit Log (Compliance & Observability)
class AuditProvider(str, Enum):
    TWILIO = "twilio"
    STRIPE = "stripe"
    SENDGRID = "sendgrid"
    GOOGLE_CALENDAR = "google_calendar"


class AuditAction(str, Enum):
    SEND_SMS = "send_sms"
    SMS_BLOCKED_NO_CONSENT = "sms_blocked_no_consent"
    SMS_OPT_OUT = "sms_opt_out"
    CHARGE_DEPOSIT = "charge_deposit"
    CREATE_PAYMENT_LINK = "create_payment_link"
    CALENDAR_CREATE = "calendar_create"
    CALENDAR_UPDATE = "calendar_update"
    CALENDAR_DELETE = "calendar_delete"
    SEND_EMAIL = "send_email"


class IntegrationAuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    shop_id: str
    provider: AuditProvider
    action: AuditAction
    entity_type: str  # client, appointment, payment
    entity_id: Optional[str] = None
    success: bool
    error_message: Optional[str] = None
    metadata: dict = Field(default_factory=dict)  # Additional context
    created_at: datetime = Field(default_factory=utc_now)

