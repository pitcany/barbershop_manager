"""
OwnerOpsAgent - Daily Summary Emails for Shop Owners
Compiles daily stats and sends a formatted HTML email via SendGrid.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from providers import get_email
from providers.interfaces import EmailMessage

logger = logging.getLogger(__name__)


class OwnerOpsAgent:
    """
    Generates and sends daily operational summary emails to the shop owner.
    
    Summary includes:
    - Appointments completed / total
    - No-shows
    - Revenue recovered (waitlist fills, deposits)
    - Cancellations
    - Waitlist activity
    - New clients
    """

    def __init__(self, db, shop: dict):
        self.db = db
        self.shop = shop
        self.shop_id = shop.get("id")
        self.shop_name = shop.get("name", "Barbershop")
        tz_name = shop.get("timezone", "America/New_York")
        try:
            self.shop_tz = ZoneInfo(tz_name)
        except (KeyError, Exception):
            self.shop_tz = ZoneInfo("UTC")

    async def _get_day_boundaries(self, target_date: datetime = None):
        """Get UTC boundaries for a given local business day."""
        if target_date is None:
            local_now = datetime.now(self.shop_tz)
            target_date = local_now - timedelta(days=1)

        day_start_local = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end_local = day_start_local + timedelta(days=1)

        day_start_utc = day_start_local.astimezone(timezone.utc)
        day_end_utc = day_end_local.astimezone(timezone.utc)

        return day_start_utc, day_end_utc, day_start_local

    async def compile_daily_stats(self, target_date: datetime = None) -> dict:
        """Compile statistics for a given day."""
        day_start, day_end, local_date = await self._get_day_boundaries(target_date)

        start_iso = day_start.isoformat()
        end_iso = day_end.isoformat()

        # Appointments
        total_appointments = await self.db.appointments.count_documents({
            "shop_id": self.shop_id,
            "scheduled_at": {"$gte": start_iso, "$lt": end_iso}
        })
        completed = await self.db.appointments.count_documents({
            "shop_id": self.shop_id,
            "scheduled_at": {"$gte": start_iso, "$lt": end_iso},
            "status": "completed"
        })
        no_shows = await self.db.appointments.count_documents({
            "shop_id": self.shop_id,
            "scheduled_at": {"$gte": start_iso, "$lt": end_iso},
            "status": "no_show"
        })
        cancelled = await self.db.appointments.count_documents({
            "shop_id": self.shop_id,
            "scheduled_at": {"$gte": start_iso, "$lt": end_iso},
            "status": "cancelled"
        })

        # Revenue from completed appointments
        revenue_pipeline = [
            {"$match": {
                "shop_id": self.shop_id,
                "scheduled_at": {"$gte": start_iso, "$lt": end_iso},
                "status": "completed"
            }},
            {"$group": {"_id": None, "total": {"$sum": "$price"}}}
        ]
        rev_result = await self.db.appointments.aggregate(revenue_pipeline).to_list(1)
        total_revenue = rev_result[0]["total"] if rev_result else 0

        # Recovered revenue events
        recovered_pipeline = [
            {"$match": {
                "shop_id": self.shop_id,
                "attributed_at": {"$gte": start_iso, "$lt": end_iso}
            }},
            {"$group": {"_id": "$source", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
        ]
        recovered_results = await self.db.recovered_revenue_events.aggregate(recovered_pipeline).to_list(10)
        recovered_by_source = {r["_id"]: {"amount": r["total"], "count": r["count"]} for r in recovered_results}
        total_recovered = sum(r["total"] for r in recovered_results)

        # Messages
        messages_sent = await self.db.messages.count_documents({
            "shop_id": self.shop_id,
            "direction": "outbound",
            "created_at": {"$gte": start_iso, "$lt": end_iso}
        })
        messages_received = await self.db.messages.count_documents({
            "shop_id": self.shop_id,
            "direction": "inbound",
            "created_at": {"$gte": start_iso, "$lt": end_iso}
        })

        # Waitlist
        waitlist_active = await self.db.waitlist.count_documents({
            "shop_id": self.shop_id, "active": True
        })

        # New clients today
        new_clients = await self.db.clients.count_documents({
            "shop_id": self.shop_id,
            "created_at": {"$gte": start_iso, "$lt": end_iso}
        })

        return {
            "date": local_date.strftime("%A, %B %d, %Y"),
            "date_short": local_date.strftime("%b %d"),
            "total_appointments": total_appointments,
            "completed": completed,
            "no_shows": no_shows,
            "cancelled": cancelled,
            "pending": total_appointments - completed - no_shows - cancelled,
            "total_revenue": total_revenue,
            "total_recovered": total_recovered,
            "recovered_by_source": recovered_by_source,
            "messages_sent": messages_sent,
            "messages_received": messages_received,
            "waitlist_active": waitlist_active,
            "new_clients": new_clients,
            "no_show_rate": round((no_shows / total_appointments * 100) if total_appointments > 0 else 0, 1),
        }

    def _build_html_email(self, stats: dict) -> str:
        """Build a formatted HTML email from stats."""
        recovered_rows = ""
        for source, data in stats.get("recovered_by_source", {}).items():
            recovered_rows += f"""
            <tr>
                <td style="padding:8px 16px; color:#a1a1aa;">{source.replace('_',' ').title()}</td>
                <td style="padding:8px 16px; color:#22c55e; text-align:right;">${data['amount']:.2f} ({data['count']})</td>
            </tr>"""

        if not recovered_rows:
            recovered_rows = """
            <tr>
                <td colspan="2" style="padding:8px 16px; color:#71717a; text-align:center;">No recovered revenue today</td>
            </tr>"""

        return f"""
        <html>
        <body style="margin:0; padding:0; background-color:#09090b; font-family:Arial, Helvetica, sans-serif;">
          <div style="max-width:600px; margin:0 auto; padding:20px;">
            <!-- Header -->
            <div style="background-color:#D4AF37; padding:24px; text-align:center; border-radius:8px 8px 0 0;">
              <h1 style="color:#000; margin:0; font-size:24px;">Daily Summary</h1>
              <p style="color:#000; margin:8px 0 0; font-size:14px;">{self.shop_name} &mdash; {stats['date']}</p>
            </div>

            <!-- Stats Grid -->
            <div style="background-color:#18181b; padding:24px; border-bottom:1px solid #27272a;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:12px; text-align:center; width:33%;">
                    <div style="color:#D4AF37; font-size:28px; font-weight:bold;">{stats['completed']}</div>
                    <div style="color:#a1a1aa; font-size:12px;">Completed</div>
                  </td>
                  <td style="padding:12px; text-align:center; width:33%;">
                    <div style="color:#ef4444; font-size:28px; font-weight:bold;">{stats['no_shows']}</div>
                    <div style="color:#a1a1aa; font-size:12px;">No-Shows</div>
                  </td>
                  <td style="padding:12px; text-align:center; width:33%;">
                    <div style="color:#22c55e; font-size:28px; font-weight:bold;">${stats['total_revenue']:.2f}</div>
                    <div style="color:#a1a1aa; font-size:12px;">Revenue</div>
                  </td>
                </tr>
              </table>
            </div>

            <!-- Appointment Breakdown -->
            <div style="background-color:#18181b; padding:20px 24px; border-bottom:1px solid #27272a;">
              <h3 style="color:#fafafa; margin:0 0 12px; font-size:16px;">Appointments</h3>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">Total Scheduled</td>
                  <td style="padding:6px 0; color:#fafafa; text-align:right;">{stats['total_appointments']}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">Completed</td>
                  <td style="padding:6px 0; color:#22c55e; text-align:right;">{stats['completed']}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">No-Shows</td>
                  <td style="padding:6px 0; color:#ef4444; text-align:right;">{stats['no_shows']} ({stats['no_show_rate']}%)</td>
                </tr>
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">Cancelled</td>
                  <td style="padding:6px 0; color:#f59e0b; text-align:right;">{stats['cancelled']}</td>
                </tr>
              </table>
            </div>

            <!-- Recovered Revenue -->
            <div style="background-color:#18181b; padding:20px 24px; border-bottom:1px solid #27272a;">
              <h3 style="color:#fafafa; margin:0 0 12px; font-size:16px;">
                Recovered Revenue: <span style="color:#22c55e;">${stats['total_recovered']:.2f}</span>
              </h3>
              <table width="100%" cellpadding="0" cellspacing="0">
                {recovered_rows}
              </table>
            </div>

            <!-- Activity -->
            <div style="background-color:#18181b; padding:20px 24px; border-bottom:1px solid #27272a;">
              <h3 style="color:#fafafa; margin:0 0 12px; font-size:16px;">Activity</h3>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">Messages Received</td>
                  <td style="padding:6px 0; color:#fafafa; text-align:right;">{stats['messages_received']}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">Messages Sent</td>
                  <td style="padding:6px 0; color:#fafafa; text-align:right;">{stats['messages_sent']}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">New Clients</td>
                  <td style="padding:6px 0; color:#fafafa; text-align:right;">{stats['new_clients']}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0; color:#a1a1aa;">Active Waitlist</td>
                  <td style="padding:6px 0; color:#fafafa; text-align:right;">{stats['waitlist_active']}</td>
                </tr>
              </table>
            </div>

            <!-- Footer -->
            <div style="background-color:#18181b; padding:16px 24px; text-align:center; border-radius:0 0 8px 8px;">
              <p style="color:#71717a; font-size:11px; margin:0;">
                Autopilot Daily Summary &mdash; Sent automatically at end of business day
              </p>
            </div>
          </div>
        </body>
        </html>
        """

    def _build_plain_email(self, stats: dict) -> str:
        """Build plain text version."""
        lines = [
            f"Daily Summary - {self.shop_name}",
            f"Date: {stats['date']}",
            "",
            f"APPOINTMENTS",
            f"  Total: {stats['total_appointments']}",
            f"  Completed: {stats['completed']}",
            f"  No-Shows: {stats['no_shows']} ({stats['no_show_rate']}%)",
            f"  Cancelled: {stats['cancelled']}",
            "",
            f"REVENUE",
            f"  Total: ${stats['total_revenue']:.2f}",
            f"  Recovered: ${stats['total_recovered']:.2f}",
            "",
            f"ACTIVITY",
            f"  Messages In: {stats['messages_received']}",
            f"  Messages Out: {stats['messages_sent']}",
            f"  New Clients: {stats['new_clients']}",
            f"  Active Waitlist: {stats['waitlist_active']}",
        ]
        return "\n".join(lines)

    async def send_daily_summary(self, target_date: datetime = None) -> dict:
        """Compile stats and send the daily summary email to the shop owner."""
        stats = await self.compile_daily_stats(target_date)

        # Determine recipient - shop owner email
        to_email = self.shop.get("email")
        if not to_email:
            logger.warning(f"No email configured for shop {self.shop_id}, skipping summary")
            return {"status": "skipped", "reason": "no_shop_email", "stats": stats}

        html = self._build_html_email(stats)
        plain = self._build_plain_email(stats)

        email_provider = get_email(self.db)
        response = await email_provider.send_email(EmailMessage(
            to=to_email,
            subject=f"Daily Summary - {stats['date_short']} | {self.shop_name}",
            html_content=html,
            plain_content=plain,
        ))

        result = {
            "status": "sent" if response.success else "failed",
            "to": to_email,
            "message_id": response.message_id,
            "error": response.error,
            "stats": stats,
        }

        # Log to audit
        await self.db.integration_audit_log.insert_one({
            "id": str(uuid.uuid4()),
            "shop_id": self.shop_id,
            "provider": "sendgrid",
            "action": "daily_summary_email",
            "success": response.success,
            "error_message": response.error,
            "metadata": {"to": to_email, "date": stats["date"]},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"Daily summary for {self.shop_id}: {result['status']}")
        return result


async def run_daily_summary_for_all_shops(db) -> dict:
    """Run the daily summary for all shops."""
    shops = await db.shops.find({}, {"_id": 0}).to_list(100)
    results = {}
    for shop_data in shops:
        agent = OwnerOpsAgent(db, shop_data)
        results[shop_data["id"]] = await agent.send_daily_summary()
    return results
