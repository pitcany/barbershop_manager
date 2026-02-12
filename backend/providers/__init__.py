"""
Provider factory - creates the appropriate provider based on environment config
"""
import os
import logging
from typing import Optional

from .interfaces import SMSProvider, CalendarProvider, EmailProvider, PaymentProvider
from .mock_providers import (
    MockSMSProvider, MockCalendarProvider, MockEmailProvider, MockPaymentProvider
)
from .real_providers import (
    TwilioSMSProvider, GoogleCalendarProvider, SendGridEmailProvider, StripePaymentProvider
)

logger = logging.getLogger(__name__)


def _is_true(value: Optional[str]) -> bool:
    """Check if env variable is truthy"""
    if not value:
        return False
    return value.lower() in ('true', '1', 'yes', 'on')


def get_sms_provider() -> SMSProvider:
    """Get SMS provider based on TWILIO_ENABLED flag"""
    twilio_enabled = _is_true(os.environ.get("TWILIO_ENABLED"))
    
    if twilio_enabled:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if account_sid and auth_token:
            logger.info("Using Twilio SMS provider")
            return TwilioSMSProvider()
        else:
            logger.warning("TWILIO_ENABLED=true but credentials missing, falling back to mock")
    
    logger.info("Using Mock SMS provider")
    return MockSMSProvider()


def get_calendar_provider(db=None) -> CalendarProvider:
    """Get calendar provider based on CALENDAR_ENABLED flag and OAuth credentials"""
    calendar_enabled = _is_true(os.environ.get("CALENDAR_ENABLED"))
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    # Check for OAuth credentials
    if calendar_enabled and client_id and client_secret:
        logger.info("Using Google Calendar provider (OAuth2)")
        return GoogleCalendarProvider(db=db)
    
    # Fall back to service account if available
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if calendar_enabled and creds_path and os.path.exists(creds_path):
        logger.info("Using Google Calendar provider (Service Account)")
        return GoogleCalendarProvider(db=db)
    
    if calendar_enabled:
        logger.warning("CALENDAR_ENABLED=true but no credentials found, falling back to mock")
    
    logger.info("Using Mock Calendar provider")
    return MockCalendarProvider()


def get_email_provider(db=None) -> EmailProvider:
    """Get email provider based on SEND_EMAILS flag"""
    send_emails = _is_true(os.environ.get("SEND_EMAILS"))
    
    if send_emails:
        api_key = os.environ.get("SENDGRID_API_KEY")
        
        if api_key:
            logger.info("Using SendGrid email provider")
            return SendGridEmailProvider()
        else:
            logger.warning("SEND_EMAILS=true but SENDGRID_API_KEY missing, falling back to mock")
    
    logger.info("Using Mock Email provider")
    return MockEmailProvider(db)


def get_payment_provider(webhook_url: str = "") -> PaymentProvider:
    """Get payment provider based on STRIPE_ENABLED flag and key availability"""
    stripe_enabled = _is_true(os.environ.get("STRIPE_ENABLED"))
    stripe_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    
    if stripe_enabled and stripe_key:
        logger.info("Using Stripe payment provider")
        return StripePaymentProvider(webhook_url)
    elif stripe_enabled:
        logger.warning("STRIPE_ENABLED=true but no API key found, falling back to mock")
    
    logger.info("Using Mock Payment provider")
    return MockPaymentProvider()


# Singleton instances (initialized lazily)
_sms_provider: Optional[SMSProvider] = None
_calendar_provider: Optional[CalendarProvider] = None
_email_provider: Optional[EmailProvider] = None
_payment_provider: Optional[PaymentProvider] = None


def get_sms() -> SMSProvider:
    global _sms_provider
    if _sms_provider is None:
        _sms_provider = get_sms_provider()
    return _sms_provider


def get_calendar() -> CalendarProvider:
    global _calendar_provider
    if _calendar_provider is None:
        _calendar_provider = get_calendar_provider()
    return _calendar_provider


def get_email(db=None) -> EmailProvider:
    global _email_provider
    if _email_provider is None:
        _email_provider = get_email_provider(db)
    return _email_provider


def get_payment(webhook_url: str = "") -> PaymentProvider:
    global _payment_provider
    if _payment_provider is None:
        _payment_provider = get_payment_provider(webhook_url)
    return _payment_provider


def reset_providers():
    """Reset all providers (useful for testing)"""
    global _sms_provider, _calendar_provider, _email_provider, _payment_provider
    _sms_provider = None
    _calendar_provider = None
    _email_provider = None
    _payment_provider = None
