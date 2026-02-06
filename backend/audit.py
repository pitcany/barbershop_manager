"""
Audit logging service for compliance and observability.
Logs all external integration attempts (SMS, payments, calendar, email).
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from models import AuditProvider, AuditAction

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Centralized audit logging for all external integrations.
    Ensures compliance and provides observability into all side effects.
    """
    
    def __init__(self, db, shop_id: str):
        self.db = db
        self.shop_id = shop_id
    
    async def log(
        self,
        provider: AuditProvider,
        action: AuditAction,
        entity_type: str,
        entity_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an integration action to the audit log."""
        import uuid
        
        log_entry = {
            "id": str(uuid.uuid4()),
            "shop_id": self.shop_id,
            "provider": provider.value,
            "action": action.value,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "success": success,
            "error_message": error_message,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            await self.db.integration_audit_log.insert_one(log_entry)
            
            # Also log to console for visibility
            status = "✓" if success else "✗"
            logger.info(
                f"[AUDIT] {status} {provider.value}/{action.value} "
                f"entity={entity_type}:{entity_id} "
                f"{'error=' + error_message if error_message else ''}"
            )
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    async def log_sms_sent(
        self,
        client_id: str,
        to_phone: str,
        message_preview: str,
        success: bool,
        message_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log an outbound SMS attempt."""
        await self.log(
            provider=AuditProvider.TWILIO,
            action=AuditAction.SEND_SMS,
            entity_type="client",
            entity_id=client_id,
            success=success,
            error_message=error,
            metadata={
                "to_phone": to_phone,
                "message_preview": message_preview[:50] + "..." if len(message_preview) > 50 else message_preview,
                "message_id": message_id
            }
        )
    
    async def log_sms_blocked(
        self,
        client_id: str,
        to_phone: str,
        reason: str
    ):
        """Log a blocked SMS due to missing consent."""
        await self.log(
            provider=AuditProvider.TWILIO,
            action=AuditAction.SMS_BLOCKED_NO_CONSENT,
            entity_type="client",
            entity_id=client_id,
            success=False,
            error_message=reason,
            metadata={"to_phone": to_phone}
        )
    
    async def log_sms_opt_out(
        self,
        client_id: str,
        phone: str
    ):
        """Log when a client opts out via STOP."""
        await self.log(
            provider=AuditProvider.TWILIO,
            action=AuditAction.SMS_OPT_OUT,
            entity_type="client",
            entity_id=client_id,
            success=True,
            metadata={"phone": phone, "action": "unsubscribed"}
        )
    
    async def log_payment_attempt(
        self,
        client_id: str,
        appointment_id: Optional[str],
        amount: float,
        success: bool,
        session_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log a Stripe payment attempt."""
        await self.log(
            provider=AuditProvider.STRIPE,
            action=AuditAction.CREATE_PAYMENT_LINK,
            entity_type="payment",
            entity_id=appointment_id,
            success=success,
            error_message=error,
            metadata={
                "client_id": client_id,
                "amount": amount,
                "session_id": session_id
            }
        )
    
    async def log_calendar_event(
        self,
        action: AuditAction,
        appointment_id: str,
        calendar_id: str,
        event_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log a Google Calendar mutation."""
        await self.log(
            provider=AuditProvider.GOOGLE_CALENDAR,
            action=action,
            entity_type="appointment",
            entity_id=appointment_id,
            success=success,
            error_message=error,
            metadata={
                "calendar_id": calendar_id,
                "event_id": event_id
            }
        )
    
    async def log_email_sent(
        self,
        to_email: str,
        subject: str,
        success: bool,
        entity_type: str = "shop",
        entity_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log an email send attempt."""
        await self.log(
            provider=AuditProvider.SENDGRID,
            action=AuditAction.SEND_EMAIL,
            entity_type=entity_type,
            entity_id=entity_id,
            success=success,
            error_message=error,
            metadata={
                "to_email": to_email,
                "subject": subject
            }
        )


def create_audit_logger(db, shop_id: str) -> AuditLogger:
    """Factory function to create an audit logger."""
    return AuditLogger(db, shop_id)
