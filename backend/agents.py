"""
Agent logic for handling SMS conversations, no-show enforcement, and waitlist filling
Deterministic template-based responses (LLM abstraction ready for future)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
import re

from models import (
    Appointment, AppointmentStatus, Client, Message, MessageDirection,
    Service, Barber, Shop, Waitlist, Event, EventType, ALLOWED_TRANSITIONS
)
from providers import get_sms, get_calendar, get_payment
from providers.interfaces import SMSMessage, CalendarEvent
from audit import create_audit_logger
from sms_compliance import create_sms_service

logger = logging.getLogger(__name__)


class MessageTemplates:
    """Pre-defined message templates"""
    
    GREETING = "Hi {name}! Thanks for reaching out to {shop_name}. How can we help you today?"
    
    BOOKING_CONFIRMATION = (
        "Your appointment is confirmed!\n"
        "📅 {date} at {time}\n"
        "✂️ {service} with {barber}\n"
        "📍 {address}\n\n"
        "Reply YES to confirm or NO to cancel."
    )
    
    DEPOSIT_REQUEST = (
        "To secure your appointment, please pay a ${amount} deposit:\n"
        "{payment_link}\n\n"
        "Your appointment will be confirmed once deposit is received."
    )
    
    DEPOSIT_RECEIVED = (
        "Thank you! Your ${amount} deposit has been received. "
        "Your appointment on {date} at {time} is now confirmed."
    )
    
    REMINDER_24H = (
        "Reminder: You have an appointment tomorrow at {time} with {barber}.\n"
        "Reply CONFIRM to confirm or RESCHEDULE if you need to change."
    )
    
    CANCELLATION_CONFIRMED = (
        "Your appointment on {date} at {time} has been cancelled. "
        "We hope to see you again soon!"
    )
    
    WAITLIST_OFFER = (
        "Good news! A slot just opened up on {date} at {time} with {barber}. "
        "Would you like to book it? Reply YES to confirm or NO to stay on waitlist."
    )
    
    WAITLIST_ADDED = (
        "You've been added to our waitlist for {date}. "
        "We'll text you if a slot opens up!"
    )
    
    NO_SHOW_WARNING = (
        "We missed you at your appointment today. "
        "Please note: A ${fee} no-show fee may apply for future bookings."
    )
    
    HELP_RESPONSE = (
        "Available commands:\n"
        "• BOOK - Schedule an appointment\n"
        "• CANCEL - Cancel your appointment\n"
        "• RESCHEDULE - Change your appointment time\n"
        "• STATUS - Check your appointment\n"
        "• HELP - Show this menu"
    )


class FrontDeskAgent:
    """
    Handles inbound SMS messages and booking logic
    Deterministic rule-based system with template responses
    """
    
    def __init__(self, db, shop: Shop):
        self.db = db
        self.shop = shop
        self.sms = get_sms()
        self.calendar = get_calendar(db)
        self.payment = get_payment()
    
    async def process_inbound_message(
        self, 
        client: Client, 
        message_content: str
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Process an inbound SMS message and generate response
        Returns (response_message, action_metadata)
        """
        content = message_content.strip().upper()
        
        # Check for command keywords
        if content in ("HELP", "?", "COMMANDS"):
            return self._format_template(MessageTemplates.HELP_RESPONSE), {"action": "help"}
        
        if content in ("CONFIRM", "YES", "Y"):
            return await self._handle_confirmation(client)
        
        if content in ("CANCEL", "NO", "N"):
            return await self._handle_cancellation(client)
        
        if content in ("RESCHEDULE", "CHANGE"):
            return await self._handle_reschedule_request(client)
        
        if content in ("BOOK", "APPOINTMENT"):
            return await self._handle_booking_request(client)
        
        if content in ("STATUS", "CHECK"):
            return await self._handle_status_check(client)
        
        # Default greeting for unrecognized messages
        return self._format_template(
            MessageTemplates.GREETING,
            name=client.name.split()[0] if client.name else "there",
            shop_name=self.shop.name
        ), {"action": "greeting"}
    
    def _is_valid_transition(self, current_status: str, new_status: str) -> bool:
        """Check if a status transition is allowed by the state machine."""
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        return new_status in allowed

    async def _handle_confirmation(self, client: Client) -> Tuple[str, Dict]:
        """Handle appointment confirmation"""
        # Find pending appointment
        appointment = await self.db.appointments.find_one({
            "shop_id": self.shop.id,
            "client_id": client.id,
            "status": {"$in": [AppointmentStatus.PENDING.value, AppointmentStatus.DEPOSIT_PAID.value]}
        }, {"_id": 0})

        if not appointment:
            return "You don't have any pending appointments to confirm.", {"action": "no_appointment"}

        current_status = appointment.get("status", "pending")
        if not self._is_valid_transition(current_status, AppointmentStatus.CONFIRMED.value):
            return "Your appointment cannot be confirmed right now.", {"action": "invalid_transition"}

        # Update appointment status
        await self.db.appointments.update_one(
            {"id": appointment["id"]},
            {
                "$set": {
                    "status": AppointmentStatus.CONFIRMED.value,
                    "confirmed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Log event
        await self._log_event(
            EventType.APPOINTMENT_CONFIRMED,
            client_id=client.id,
            appointment_id=appointment["id"]
        )
        
        scheduled = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
        return (
            f"Great! Your appointment on {scheduled.strftime('%B %d')} at "
            f"{scheduled.strftime('%I:%M %p')} is confirmed. See you then!"
        ), {"action": "confirmed", "appointment_id": appointment["id"]}
    
    async def _handle_cancellation(self, client: Client) -> Tuple[str, Dict]:
        """Handle appointment cancellation"""
        appointment = await self.db.appointments.find_one({
            "shop_id": self.shop.id,
            "client_id": client.id,
            "status": {"$in": [
                AppointmentStatus.PENDING.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.DEPOSIT_PAID.value
            ]}
        }, {"_id": 0})

        if not appointment:
            return "You don't have any active appointments to cancel.", {"action": "no_appointment"}

        current_status = appointment.get("status", "pending")
        if not self._is_valid_transition(current_status, AppointmentStatus.CANCELLED.value):
            return "Your appointment cannot be cancelled at this time.", {"action": "invalid_transition"}

        # Update appointment status
        await self.db.appointments.update_one(
            {"id": appointment["id"]},
            {
                "$set": {
                    "status": AppointmentStatus.CANCELLED.value,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Log event
        await self._log_event(
            EventType.APPOINTMENT_CANCELLED,
            client_id=client.id,
            appointment_id=appointment["id"]
        )
        
        scheduled = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
        return self._format_template(
            MessageTemplates.CANCELLATION_CONFIRMED,
            date=scheduled.strftime('%B %d'),
            time=scheduled.strftime('%I:%M %p')
        ), {"action": "cancelled", "appointment_id": appointment["id"]}
    
    async def _handle_reschedule_request(self, client: Client) -> Tuple[str, Dict]:
        """Handle reschedule request"""
        return (
            "To reschedule, please call us or reply with your preferred date and time. "
            "Example: 'Saturday 2pm'"
        ), {"action": "reschedule_request"}
    
    async def _handle_booking_request(self, client: Client) -> Tuple[str, Dict]:
        """Handle new booking request"""
        # Get available services
        services = await self.db.services.find(
            {"shop_id": self.shop.id, "active": True},
            {"_id": 0}
        ).to_list(10)
        
        if not services:
            return "Sorry, no services are currently available.", {"action": "no_services"}
        
        service_list = "\n".join([
            f"{i+1}. {s['name']} (${s['price']}, {s['duration_minutes']}min)"
            for i, s in enumerate(services)
        ])
        
        return (
            f"Great! Here are our available services:\n{service_list}\n\n"
            "Reply with the number of the service you'd like to book."
        ), {"action": "booking_started", "services": [s["id"] for s in services]}
    
    async def _handle_status_check(self, client: Client) -> Tuple[str, Dict]:
        """Handle appointment status check"""
        appointment = await self.db.appointments.find_one({
            "shop_id": self.shop.id,
            "client_id": client.id,
            "status": {"$in": [
                AppointmentStatus.PENDING.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.DEPOSIT_PAID.value,
                AppointmentStatus.DEPOSIT_PENDING.value
            ]}
        }, {"_id": 0})
        
        if not appointment:
            return "You don't have any upcoming appointments.", {"action": "no_appointment"}
        
        scheduled = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
        status = appointment["status"].replace("_", " ").title()
        
        return (
            f"Your appointment:\n"
            f"📅 {scheduled.strftime('%B %d, %Y')} at {scheduled.strftime('%I:%M %p')}\n"
            f"Status: {status}"
        ), {"action": "status_checked", "appointment_id": appointment["id"]}
    
    async def _log_event(
        self,
        event_type: EventType,
        client_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        data: Optional[Dict] = None,
        revenue_impact: float = 0.0
    ):
        """Log an event to the database"""
        event = {
            "id": str(__import__("uuid").uuid4()),
            "shop_id": self.shop.id,
            "event_type": event_type.value,
            "client_id": client_id,
            "appointment_id": appointment_id,
            "data": data or {},
            "revenue_impact": revenue_impact,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await self.db.events.insert_one(event)
    
    def _format_template(self, template: str, **kwargs) -> str:
        """Format a message template with variables"""
        try:
            return template.format(**kwargs)
        except KeyError:
            return template


class NoShowEnforcementAgent:
    """
    Handles deposit requests and no-show detection
    """
    
    def __init__(self, db, shop: Shop):
        self.db = db
        self.shop = shop
        self.sms = get_sms()
        self.payment = get_payment()
    
    async def check_deposit_requirement(self, appointment: Dict, client: Dict) -> bool:
        """
        Check if deposit is required for this appointment
        Rules:
        - If booking within deposit_required_hours of appointment time
        - If client has previous no-shows
        """
        scheduled = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
        hours_until = (scheduled - datetime.now(timezone.utc)).total_seconds() / 3600
        
        # Require deposit if booking close to appointment time
        if hours_until < self.shop.deposit_required_hours:
            return True
        
        # Require deposit if client has previous no-shows
        if client.get("no_shows", 0) > 0:
            return True
        
        return False
    
    async def create_deposit_request(
        self,
        appointment_id: str,
        client: Dict,
        amount: float,
        host_url: str
    ) -> str:
        """Create a payment link for deposit"""
        success_url = f"{host_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment_id={appointment_id}"
        cancel_url = f"{host_url}/payment/cancel?appointment_id={appointment_id}"
        
        payment_link = await self.payment.create_payment_link(
            amount=amount,
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "appointment_id": appointment_id,
                "client_id": client["id"],
                "type": "deposit"
            }
        )
        
        # Update appointment with deposit info
        await self.db.appointments.update_one(
            {"id": appointment_id},
            {
                "$set": {
                    "deposit_required": True,
                    "deposit_amount": amount,
                    "status": AppointmentStatus.DEPOSIT_PENDING.value,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Create payment record
        await self.db.payments.insert_one({
            "id": str(__import__("uuid").uuid4()),
            "shop_id": self.shop.id,
            "client_id": client["id"],
            "appointment_id": appointment_id,
            "amount": amount,
            "currency": "usd",
            "stripe_session_id": payment_link.session_id,
            "status": "pending",
            "payment_type": "deposit",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        return payment_link.url
    
    async def process_no_show(self, appointment_id: str):
        """Handle no-show side-effects (client stats, revenue event).

        NOTE: The caller (update_appointment_status endpoint) already sets the
        appointment status to 'no_show'.  This method must NOT re-write the
        status to avoid a race condition with concurrent requests.
        """
        appointment = await self.db.appointments.find_one(
            {"id": appointment_id, "shop_id": self.shop.id},
            {"_id": 0}
        )

        if not appointment:
            return

        # Update client no-show count
        await self.db.clients.update_one(
            {"id": appointment["client_id"], "shop_id": self.shop.id},
            {
                "$inc": {"no_shows": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )

        # Log event with revenue impact
        service = await self.db.services.find_one(
            {"id": appointment["service_id"], "shop_id": self.shop.id},
            {"_id": 0}
        )
        revenue_lost = service["price"] if service else 0
        
        await self.db.events.insert_one({
            "id": str(__import__("uuid").uuid4()),
            "shop_id": self.shop.id,
            "event_type": EventType.NO_SHOW_DETECTED.value,
            "client_id": appointment["client_id"],
            "appointment_id": appointment_id,
            "data": {"revenue_lost": revenue_lost},
            "revenue_impact": -revenue_lost,
            "created_at": datetime.now(timezone.utc).isoformat()
        })


class WaitlistFillAgent:
    """
    Handles filling cancelled slots from waitlist
    """

    def __init__(self, db, shop: Shop):
        self.db = db
        self.shop = shop
        self.sms = get_sms()
        # Initialize compliance service for audited SMS sending
        audit_logger = create_audit_logger(db, shop.id)
        self.sms_service = create_sms_service(db, shop.id, audit_logger)
    
    async def find_waitlist_matches(
        self,
        cancelled_appointment: Dict
    ) -> List[Dict]:
        """Find waitlist entries that match the cancelled slot"""
        scheduled = datetime.fromisoformat(cancelled_appointment["scheduled_at"].replace("Z", "+00:00"))
        
        # Find waitlist entries for similar time
        matches = await self.db.waitlist.find({
            "shop_id": self.shop.id,
            "active": True,
            "service_id": cancelled_appointment["service_id"],
            "$or": [
                {"barber_id": cancelled_appointment["barber_id"]},
                {"barber_id": None}  # No preference
            ]
        }, {"_id": 0}).to_list(10)
        
        # Filter by time flexibility
        valid_matches = []
        for entry in matches:
            preferred = datetime.fromisoformat(entry["preferred_date"].replace("Z", "+00:00"))
            flexibility = entry.get("flexible_hours", 2)
            
            time_diff = abs((scheduled - preferred).total_seconds() / 3600)
            if time_diff <= flexibility:
                valid_matches.append(entry)
        
        # Sort by priority (fewer contact attempts first)
        valid_matches.sort(key=lambda x: x.get("contact_attempts", 0))
        
        return valid_matches
    
    async def offer_slot_to_waitlist(
        self,
        cancelled_appointment: Dict,
        waitlist_entry: Dict
    ) -> bool:
        """Send offer to waitlist client"""
        client = await self.db.clients.find_one(
            {"id": waitlist_entry["client_id"]},
            {"_id": 0}
        )
        
        if not client:
            return False

        barber = await self.db.barbers.find_one(
            {"id": cancelled_appointment["barber_id"]},
            {"_id": 0}
        )

        scheduled = datetime.fromisoformat(cancelled_appointment["scheduled_at"].replace("Z", "+00:00"))

        message = MessageTemplates.WAITLIST_OFFER.format(
            date=scheduled.strftime('%B %d'),
            time=scheduled.strftime('%I:%M %p'),
            barber=barber["name"] if barber else "our team"
        )

        # Send SMS through compliance service (checks consent + audit logs)
        response = await self.sms_service.send_sms(
            client_id=client["id"],
            to_phone=client["phone"],
            message=message,
        )

        if not response.success:
            logger.warning(f"Waitlist SMS blocked for client {client['id']}: {response.error}")
            return False
        
        # Update waitlist entry
        await self.db.waitlist.update_one(
            {"id": waitlist_entry["id"]},
            {
                "$inc": {"contact_attempts": 1},
                "$set": {"last_contacted": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        # Log message
        await self.db.messages.insert_one({
            "id": str(__import__("uuid").uuid4()),
            "shop_id": self.shop.id,
            "client_id": client["id"],
            "direction": MessageDirection.OUTBOUND.value,
            "message_type": "sms",
            "content": message,
            "twilio_sid": response.message_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        return response.success
    
    async def process_cancellation(self, appointment_id: str):
        """Process a cancellation and attempt to fill from waitlist"""
        appointment = await self.db.appointments.find_one(
            {"id": appointment_id, "shop_id": self.shop.id},
            {"_id": 0}
        )
        
        if not appointment:
            return
        
        # Find matching waitlist entries
        matches = await self.find_waitlist_matches(appointment)
        
        # Attempt to fill with first match
        for match in matches:
            if await self.offer_slot_to_waitlist(appointment, match):
                logger.info(f"Offered cancelled slot to waitlist client {match['client_id']}")
                break
