"""
SMS Compliance Service
Enforces consent requirements and handles opt-out (STOP) processing.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from providers import get_sms
from providers.interfaces import SMSMessage, SMSResponse
from audit import AuditLogger

logger = logging.getLogger(__name__)

# Opt-out keywords per CTIA Short Code Monitoring Handbook (case-insensitive)
OPT_OUT_KEYWORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "END", "QUIT"}

# Confirmation message for opt-out
OPT_OUT_CONFIRMATION = "You have been unsubscribed and will no longer receive messages."


def is_opt_out_message(message: str) -> bool:
    """Check if message is an opt-out request."""
    return message.strip().upper() in OPT_OUT_KEYWORDS


def is_twilio_enabled() -> bool:
    """Check if Twilio is enabled via environment."""
    return os.environ.get("TWILIO_ENABLED", "").lower() in ("true", "1", "yes")


class SMSComplianceService:
    """
    Handles SMS sending with compliance enforcement.
    - Blocks sends to clients without consent
    - Handles STOP/opt-out processing
    - Audits all SMS attempts
    """
    
    def __init__(self, db, shop_id: str, audit_logger: AuditLogger):
        self.db = db
        self.shop_id = shop_id
        self.audit = audit_logger
        self.sms_provider = get_sms()
    
    async def check_consent(self, client_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if client has SMS consent.
        Returns (has_consent, reason_if_blocked)
        """
        client = await self.db.clients.find_one(
            {"id": client_id, "shop_id": self.shop_id},
            {"_id": 0, "sms_consent": 1, "phone": 1}
        )
        
        if not client:
            return False, "Client not found"
        
        if not client.get("sms_consent", False):
            return False, "SMS consent not granted"
        
        return True, None
    
    async def send_sms(
        self,
        client_id: str,
        to_phone: str,
        message: str,
        bypass_consent: bool = False  # Only for opt-out confirmation
    ) -> SMSResponse:
        """
        Send SMS with compliance checks.
        
        Args:
            client_id: The client ID
            to_phone: Destination phone number
            message: Message content
            bypass_consent: If True, skip consent check (for opt-out confirmation only)
        
        Returns:
            SMSResponse with success/failure status
        """
        # Check consent unless bypassing (for opt-out confirmation)
        if not bypass_consent:
            has_consent, reason = await self.check_consent(client_id)
            
            if not has_consent:
                # Log blocked attempt
                await self.audit.log_sms_blocked(
                    client_id=client_id,
                    to_phone=to_phone,
                    reason=reason
                )
                
                logger.warning(f"SMS blocked to {to_phone}: {reason}")
                
                return SMSResponse(
                    success=False,
                    error=f"SMS blocked: {reason}"
                )
        
        # Check if Twilio is enabled
        if not is_twilio_enabled():
            # Log the attempt but don't actually send
            await self.audit.log_sms_sent(
                client_id=client_id,
                to_phone=to_phone,
                message_preview=message,
                success=False,
                error="TWILIO_ENABLED=false (simulation mode)"
            )
            
            logger.info(f"[MOCK SMS] To: {to_phone} | Message: {message[:50]}...")
            
            # Return success for business logic to continue
            return SMSResponse(
                success=True,
                message_id=f"mock_disabled_{datetime.now().timestamp()}"
            )
        
        # Send via Twilio
        try:
            response = await self.sms_provider.send_sms(SMSMessage(
                to=to_phone,
                body=message
            ))
            
            # Log the attempt
            await self.audit.log_sms_sent(
                client_id=client_id,
                to_phone=to_phone,
                message_preview=message,
                success=response.success,
                message_id=response.message_id,
                error=response.error
            )
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            
            await self.audit.log_sms_sent(
                client_id=client_id,
                to_phone=to_phone,
                message_preview=message,
                success=False,
                error=error_msg
            )
            
            return SMSResponse(success=False, error=error_msg)
    
    async def process_opt_out(self, client_id: str, phone: str) -> bool:
        """
        Process an opt-out request (STOP).
        - Sets sms_consent = false
        - Sends confirmation message
        - Logs the opt-out
        
        Returns True if processed successfully.
        """
        # Update client consent status
        result = await self.db.clients.update_one(
            {"id": client_id, "shop_id": self.shop_id},
            {
                "$set": {
                    "sms_consent": False,
                    "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
                    "sms_consent_source": "opt_out_stop",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        if result.modified_count == 0:
            logger.warning(f"Failed to update consent for client {client_id}")
            return False
        
        # Log the opt-out
        await self.audit.log_sms_opt_out(client_id, phone)
        
        # Send confirmation (bypass consent since they just opted out)
        await self.send_sms(
            client_id=client_id,
            to_phone=phone,
            message=OPT_OUT_CONFIRMATION,
            bypass_consent=True  # This is the one allowed message after opt-out
        )
        
        logger.info(f"Client {client_id} ({phone}) opted out of SMS")
        
        return True
    
    async def grant_consent(
        self,
        client_id: str,
        source: str = "unknown"
    ) -> bool:
        """
        Grant SMS consent for a client.
        
        Args:
            client_id: The client ID
            source: How consent was obtained (web_form, inbound_sms, manual)
        
        Returns True if updated successfully.
        """
        result = await self.db.clients.update_one(
            {"id": client_id, "shop_id": self.shop_id},
            {
                "$set": {
                    "sms_consent": True,
                    "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
                    "sms_consent_source": source,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return result.modified_count > 0


def create_sms_service(db, shop_id: str, audit_logger: AuditLogger) -> SMSComplianceService:
    """Factory function to create SMS compliance service."""
    return SMSComplianceService(db, shop_id, audit_logger)
