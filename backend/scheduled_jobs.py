"""
Scheduled Jobs for Barbershop Autopilot
Appointment reminders and other periodic tasks.

Uses the SMS compliance service to ensure consent is checked before sending.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from models import Shop, Client, Appointment, AppointmentStatus, MessageDirection
from audit import create_audit_logger
from sms_compliance import create_sms_service

logger = logging.getLogger(__name__)


class AppointmentReminderJob:
    """
    Sends appointment reminders to clients with confirmed appointments.
    
    Respects:
    - SMS consent (via SMSComplianceService)
    - Shop's confirmation_window_hours setting
    - Rate limiting (max_messages_per_day)
    """
    
    def __init__(self, db, shop: Shop):
        self.db = db
        self.shop = shop
        self.audit_logger = create_audit_logger(db, shop.id)
        self.sms_service = create_sms_service(db, shop.id, self.audit_logger)
    
    async def get_appointments_needing_reminder(self) -> list:
        """
        Find appointments that need a reminder sent.
        
        Criteria:
        - Status is CONFIRMED or DEPOSIT_PAID
        - Scheduled within the confirmation window (e.g., next 24 hours)
        - No reminder already sent (check messages)
        """
        now = datetime.now(timezone.utc)
        window_hours = self.shop.confirmation_window_hours
        
        # Find appointments in the reminder window
        window_start = now
        window_end = now + timedelta(hours=window_hours)
        
        appointments = await self.db.appointments.find({
            "shop_id": self.shop.id,
            "status": {"$in": [
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.DEPOSIT_PAID.value
            ]},
            "scheduled_at": {
                "$gte": window_start.isoformat(),
                "$lte": window_end.isoformat()
            }
        }, {"_id": 0}).to_list(100)
        
        # Filter out appointments that already have a reminder
        appointments_needing_reminder = []
        for apt in appointments:
            # Check if reminder was already sent
            reminder_exists = await self.db.messages.find_one({
                "shop_id": self.shop.id,
                "client_id": apt["client_id"],
                "appointment_id": apt["id"],
                "direction": MessageDirection.OUTBOUND.value,
                "content": {"$regex": "Reminder:"}
            })
            
            if not reminder_exists:
                appointments_needing_reminder.append(apt)
        
        return appointments_needing_reminder
    
    async def send_reminder(self, appointment: dict) -> bool:
        """
        Send a reminder for a single appointment.
        
        Returns True if sent successfully, False otherwise.
        """
        # Get client
        client = await self.db.clients.find_one(
            {"id": appointment["client_id"]},
            {"_id": 0}
        )
        
        if not client:
            logger.warning(f"Client not found for appointment {appointment['id']}")
            return False
        
        # Get barber name
        barber = await self.db.barbers.find_one(
            {"id": appointment["barber_id"]},
            {"_id": 0, "name": 1}
        )
        barber_name = barber["name"] if barber else "your barber"
        
        # Get service name
        service = await self.db.services.find_one(
            {"id": appointment["service_id"]},
            {"_id": 0, "name": 1}
        )
        service_name = service["name"] if service else "your appointment"
        
        # Parse scheduled time
        scheduled = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
        
        # Format reminder message
        message = (
            f"Reminder: You have an appointment tomorrow at {scheduled.strftime('%I:%M %p')} "
            f"with {barber_name} for {service_name}.\n"
            f"Reply CONFIRM to confirm or RESCHEDULE if you need to change."
        )
        
        # Send via compliance service (checks consent automatically)
        response = await self.sms_service.send_sms(
            client_id=client["id"],
            to_phone=client["phone"],
            message=message
        )
        
        if response.success:
            # Store the message
            import uuid
            await self.db.messages.insert_one({
                "id": str(uuid.uuid4()),
                "shop_id": self.shop.id,
                "client_id": client["id"],
                "appointment_id": appointment["id"],
                "direction": MessageDirection.OUTBOUND.value,
                "message_type": "sms",
                "content": message,
                "twilio_sid": response.message_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Sent reminder for appointment {appointment['id']} to {client['phone']}")
            return True
        else:
            logger.warning(f"Failed to send reminder for appointment {appointment['id']}: {response.error}")
            return False
    
    async def run(self) -> dict:
        """
        Run the reminder job.
        
        Returns a summary of actions taken.
        """
        logger.info(f"Running appointment reminder job for shop {self.shop.id}")
        
        appointments = await self.get_appointments_needing_reminder()
        
        results = {
            "total_found": len(appointments),
            "sent": 0,
            "failed": 0,
            "blocked": 0
        }
        
        for apt in appointments:
            success = await self.send_reminder(apt)
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"Reminder job complete: {results}")
        return results


async def run_reminder_job_for_all_shops(db) -> dict:
    """
    Run the reminder job for all active shops.
    """
    shops = await db.shops.find({}, {"_id": 0}).to_list(100)
    
    all_results = {}
    for shop_data in shops:
        shop = Shop(**shop_data)
        job = AppointmentReminderJob(db, shop)
        results = await job.run()
        all_results[shop.id] = results
    
    return all_results


# ============================================================
# Standalone runner for cron/scheduler
# ============================================================

async def main():
    """
    Main entry point for running reminder job standalone.
    Can be called from cron or a scheduler.
    """
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    
    # Connect to MongoDB
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'barbershop_autopilot')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    try:
        results = await run_reminder_job_for_all_shops(db)
        print(f"Reminder job results: {results}")
        return results
    finally:
        client.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())
