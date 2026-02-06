"""
Recovered Revenue Logger
Internal instrumentation for tracking revenue recovery events.

This module logs revenue events for internal attribution only.
Data is NOT surfaced in:
- Owner emails
- UI/Dashboards  
- SMS messages

Events are logged reliably but logging failures never block normal operation.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional
import uuid

from models import RevenueSource

logger = logging.getLogger(__name__)


def _is_provider_mocked(provider: str) -> bool:
    """Check if a provider is running in mock mode."""
    flags = {
        "twilio": os.environ.get("TWILIO_ENABLED", "false"),
        "stripe": os.environ.get("STRIPE_ENABLED", "false"),
        "calendar": os.environ.get("CALENDAR_ENABLED", "false"),
    }
    return flags.get(provider, "false").lower() not in ("true", "1", "yes")


class RecoveredRevenueLogger:
    """
    Logs recovered revenue events for internal attribution.
    
    Events are immutable once written.
    Logging failures are caught and logged but never block normal operation.
    """
    
    def __init__(self, db, shop_id: str):
        self.db = db
        self.shop_id = shop_id
    
    async def log_waitlist_fill(
        self,
        appointment_id: str,
        client_id: str,
        amount: float,
        currency: str = "usd",
        is_same_day: bool = True
    ) -> bool:
        """
        Log a waitlist fill revenue recovery event.
        
        Only logs if:
        - Replacement appointment is on the same calendar day
        - Service has a known price (amount > 0)
        
        Returns True if logged successfully, False otherwise.
        """
        # Only log same-day fills per requirements
        if not is_same_day:
            logger.debug(f"Skipping waitlist fill log - not same day: {appointment_id}")
            return False
        
        # Only log if there's actual revenue
        if amount <= 0:
            logger.debug(f"Skipping waitlist fill log - no revenue amount: {appointment_id}")
            return False
        
        notes = None
        if _is_provider_mocked("twilio") or _is_provider_mocked("calendar"):
            notes = "mocked_execution=true"
        
        return await self._log_event(
            source=RevenueSource.WAITLIST_FILL,
            appointment_id=appointment_id,
            client_id=client_id,
            amount=amount,
            currency=currency,
            notes=notes
        )
    
    async def log_no_show_fee(
        self,
        appointment_id: str,
        client_id: str,
        amount: float,
        currency: str = "usd",
        payment_id: Optional[str] = None
    ) -> bool:
        """
        Log a no-show fee collection revenue recovery event.
        
        Only logs if:
        - A deposit or no-show fee was successfully charged
        - Amount > 0
        
        Returns True if logged successfully, False otherwise.
        """
        # Only log if there's actual fee collected
        if amount <= 0:
            logger.debug(f"Skipping no-show fee log - no amount: {appointment_id}")
            return False
        
        notes = None
        if _is_provider_mocked("stripe"):
            notes = "mocked_execution=true"
        
        if payment_id:
            notes = f"{notes}, payment_id={payment_id}" if notes else f"payment_id={payment_id}"
        
        return await self._log_event(
            source=RevenueSource.NO_SHOW_FEE,
            appointment_id=appointment_id,
            client_id=client_id,
            amount=amount,
            currency=currency,
            notes=notes
        )
    
    async def _log_event(
        self,
        source: RevenueSource,
        amount: float,
        currency: str,
        appointment_id: Optional[str] = None,
        client_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Internal method to write an immutable revenue event record.
        
        Failures are caught and logged but never raise exceptions.
        """
        try:
            event = {
                "id": str(uuid.uuid4()),
                "shop_id": self.shop_id,
                "source": source.value,
                "appointment_id": appointment_id,
                "client_id": client_id,
                "amount": amount,
                "currency": currency,
                "attributed_at": datetime.now(timezone.utc).isoformat(),
                "notes": notes
            }
            
            await self.db.recovered_revenue_events.insert_one(event)
            
            logger.info(
                f"[REVENUE] Logged {source.value}: "
                f"${amount:.2f} {currency.upper()} "
                f"appointment={appointment_id} client={client_id}"
                f"{' (' + notes + ')' if notes else ''}"
            )
            
            return True
            
        except Exception as e:
            # Logging failures must never block normal operation
            logger.error(f"[REVENUE] Failed to log {source.value} event: {e}")
            return False


def create_revenue_logger(db, shop_id: str) -> RecoveredRevenueLogger:
    """Factory function to create a revenue logger."""
    return RecoveredRevenueLogger(db, shop_id)
