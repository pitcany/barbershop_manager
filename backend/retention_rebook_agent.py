"""
RetentionRebookAgent - Re-engage lapsed clients
Email-first, SMS only for high-signal clients. Light touch that escalates.

Multi-touch escalation:
  Touch 1 (at lapse threshold):     Friendly email reminder
  Touch 2 (threshold + 1 week):     Warmer follow-up email
  Touch 3 (threshold + 2 weeks):    SMS for high-signal clients only

High-signal = 3+ completed appointments in history.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from providers import get_email, get_sms
from providers.interfaces import EmailMessage, SMSMessage

logger = logging.getLogger(__name__)

# Defaults (overridden by shop settings)
DEFAULT_LAPSE_WEEKS = 4
DEFAULT_COOLDOWN_DAYS = 7
HIGH_SIGNAL_MIN_VISITS = 3


class RetentionRebookAgent:

    def __init__(self, db, shop: dict):
        self.db = db
        self.shop = shop
        self.shop_id = shop.get("id")
        self.shop_name = shop.get("name", "Barbershop")
        self.shop_phone = shop.get("phone", "")
        self.lapse_weeks = shop.get("retention_lapse_weeks", DEFAULT_LAPSE_WEEKS)
        self.cooldown_days = shop.get("retention_cooldown_days", DEFAULT_COOLDOWN_DAYS)
        self.enabled = shop.get("retention_enabled", True)

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def _email_touch1(self, name: str) -> tuple:
        """Friendly first touch."""
        subject = f"Hey {name}, it's been a while!"
        html = f"""
        <div style="font-family:Arial,sans-serif; max-width:500px; margin:0 auto; padding:24px; background:#09090b; color:#fafafa; border-radius:8px;">
          <h2 style="color:#D4AF37; margin:0 0 16px;">Hey {name},</h2>
          <p style="color:#a1a1aa; line-height:1.6;">
            We noticed it's been a little while since your last visit to <strong style="color:#fafafa;">{self.shop_name}</strong>.
            Just wanted to check in — your chair is always ready when you are.
          </p>
          <p style="color:#a1a1aa; line-height:1.6;">
            Give us a call or text <strong style="color:#fafafa;">{self.shop_phone}</strong> to book your next appointment.
          </p>
          <p style="color:#71717a; font-size:12px; margin-top:24px;">— The {self.shop_name} Team</p>
        </div>
        """
        return subject, html

    def _email_touch2(self, name: str) -> tuple:
        """Warmer follow-up."""
        subject = f"{name}, we'd love to see you again"
        html = f"""
        <div style="font-family:Arial,sans-serif; max-width:500px; margin:0 auto; padding:24px; background:#09090b; color:#fafafa; border-radius:8px;">
          <h2 style="color:#D4AF37; margin:0 0 16px;">We miss you, {name}!</h2>
          <p style="color:#a1a1aa; line-height:1.6;">
            It's been a while since you've been in, and we wanted to make sure everything's alright.
            Whether you're due for a fresh cut or just want to switch things up,
            we've got you covered at <strong style="color:#fafafa;">{self.shop_name}</strong>.
          </p>
          <p style="color:#a1a1aa; line-height:1.6;">
            Text or call us at <strong style="color:#fafafa;">{self.shop_phone}</strong> — we'll get you in quick.
          </p>
          <p style="color:#71717a; font-size:12px; margin-top:24px;">— The {self.shop_name} Team</p>
        </div>
        """
        return subject, html

    def _sms_touch3(self, name: str) -> str:
        """SMS for high-signal clients only."""
        return (
            f"Hey {name}, it's {self.shop_name}. "
            f"It's been a while — your chair misses you! "
            f"Text us back or call {self.shop_phone} to book."
        )

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------
    async def find_lapsed_clients(self) -> list:
        """Find clients whose last completed appointment was beyond the lapse threshold."""
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(weeks=self.lapse_weeks)

        # Get all clients for this shop
        clients = await self.db.clients.find(
            {"shop_id": self.shop_id}, {"_id": 0}
        ).to_list(1000)

        lapsed = []
        for client in clients:
            client_id = client["id"]

            # Find their most recent completed appointment
            last_apt = await self.db.appointments.find_one(
                {"shop_id": self.shop_id, "client_id": client_id, "status": "completed"},
                {"_id": 0, "scheduled_at": 1},
                sort=[("scheduled_at", -1)],
            )
            if not last_apt:
                continue  # Never completed an appointment — skip

            last_visit_str = last_apt.get("scheduled_at", "")
            try:
                last_visit = datetime.fromisoformat(last_visit_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            if last_visit >= threshold:
                continue  # Visited recently — not lapsed

            # Check if we already reached out recently (cooldown)
            recent_outreach = await self.db.retention_outreach.find_one({
                "shop_id": self.shop_id,
                "client_id": client_id,
                "created_at": {"$gte": (now - timedelta(days=self.cooldown_days)).isoformat()},
            })

            # Count total completed visits (for signal strength)
            completed_count = await self.db.appointments.count_documents({
                "shop_id": self.shop_id, "client_id": client_id, "status": "completed"
            })

            # Determine current touch level
            outreach_count = await self.db.retention_outreach.count_documents({
                "shop_id": self.shop_id, "client_id": client_id
            })

            days_since = (now - last_visit).days
            touch = outreach_count + 1  # Next touch number

            lapsed.append({
                "client_id": client_id,
                "name": client.get("name", "Client"),
                "email": client.get("email"),
                "phone": client.get("phone"),
                "sms_consent": client.get("sms_consent", False),
                "completed_visits": completed_count,
                "days_since_last_visit": days_since,
                "last_visit": last_visit_str,
                "next_touch": touch,
                "high_signal": completed_count >= HIGH_SIGNAL_MIN_VISITS,
                "in_cooldown": recent_outreach is not None,
            })

        return lapsed

    async def _send_email(self, client: dict, touch: int) -> dict:
        """Send retention email for given touch level."""
        name = client["name"].split()[0]  # First name only
        email = client.get("email")
        if not email:
            return {"action": "skipped", "reason": "no_email"}

        if touch <= 1:
            subject, html = self._email_touch1(name)
        else:
            subject, html = self._email_touch2(name)

        email_provider = get_email(self.db)
        response = await email_provider.send_email(EmailMessage(
            to=email,
            subject=subject,
            html_content=html,
            plain_content=f"Hey {name}, it's been a while since your last visit to {self.shop_name}. Text or call {self.shop_phone} to book.",
        ))

        return {
            "action": "email_sent",
            "touch": touch,
            "success": response.success,
            "error": response.error,
        }

    async def _send_sms(self, client: dict) -> dict:
        """Send retention SMS (touch 3, high-signal only)."""
        phone = client.get("phone")
        if not phone:
            return {"action": "skipped", "reason": "no_phone"}
        if not client.get("sms_consent"):
            return {"action": "skipped", "reason": "no_sms_consent"}

        name = client["name"].split()[0]
        body = self._sms_touch3(name)

        sms_provider = get_sms(self.db)
        response = await sms_provider.send_sms(SMSMessage(
            to=phone, body=body, from_number=self.shop_phone,
        ))

        return {
            "action": "sms_sent",
            "touch": 3,
            "success": response.success,
            "error": response.error,
        }

    async def _log_outreach(self, client_id: str, channel: str, touch: int, success: bool, error: str = None):
        """Record the outreach attempt."""
        await self.db.retention_outreach.insert_one({
            "id": str(uuid.uuid4()),
            "shop_id": self.shop_id,
            "client_id": client_id,
            "channel": channel,
            "touch": touch,
            "success": success,
            "error": error,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    async def run(self) -> dict:
        """
        Execute the retention sweep.
        Returns a summary of actions taken.
        """
        if not self.enabled:
            return {"status": "disabled", "actions": []}

        lapsed = await self.find_lapsed_clients()
        actions = []

        for client in lapsed:
            if client["in_cooldown"]:
                actions.append({
                    "client_id": client["client_id"],
                    "name": client["name"],
                    "action": "skipped_cooldown",
                    "days_since": client["days_since_last_visit"],
                })
                continue

            touch = client["next_touch"]
            result = None

            if touch <= 2:
                # Touch 1-2: email only
                result = await self._send_email(client, touch)
                if result.get("success"):
                    await self._log_outreach(client["client_id"], "email", touch, True)
                else:
                    await self._log_outreach(client["client_id"], "email", touch, False, result.get("error"))

            elif touch >= 3 and client["high_signal"]:
                # Touch 3+: SMS for high-signal clients
                result = await self._send_sms(client)
                if result.get("success"):
                    await self._log_outreach(client["client_id"], "sms", touch, True)
                else:
                    await self._log_outreach(client["client_id"], "sms", touch, False, result.get("error"))

            else:
                result = {"action": "skipped", "reason": "max_touches_for_low_signal"}

            actions.append({
                "client_id": client["client_id"],
                "name": client["name"],
                "days_since": client["days_since_last_visit"],
                "completed_visits": client["completed_visits"],
                "high_signal": client["high_signal"],
                **result,
            })

        return {
            "status": "completed",
            "lapsed_found": len(lapsed),
            "actions_taken": len([a for a in actions if a.get("action") not in ("skipped_cooldown", "skipped")]),
            "actions": actions,
        }


async def run_retention_for_all_shops(db) -> dict:
    """Run retention sweep for all shops."""
    shops = await db.shops.find({}, {"_id": 0}).to_list(100)
    results = {}
    for shop_data in shops:
        agent = RetentionRebookAgent(db, shop_data)
        results[shop_data["id"]] = await agent.run()
    return results
