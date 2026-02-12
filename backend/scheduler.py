"""
Background Scheduler for Barbershop Autopilot
Uses APScheduler to run periodic tasks in-process.

Tasks:
- Appointment reminders: every hour
- Daily summary email: once per day at configured time
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Module-level scheduler instance
_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def _run_reminders(db):
    """Task: send appointment reminders for all shops."""
    from scheduled_jobs import run_reminder_job_for_all_shops
    try:
        results = await run_reminder_job_for_all_shops(db)
        logger.info(f"[SCHEDULER] Reminder job results: {results}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Reminder job failed: {e}")


async def _run_daily_summary(db):
    """Task: send daily summary emails for all shops."""
    from owner_ops_agent import run_daily_summary_for_all_shops
    try:
        results = await run_daily_summary_for_all_shops(db)
        logger.info(f"[SCHEDULER] Daily summary results: {results}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Daily summary failed: {e}")


def start_scheduler(db):
    """
    Start the background scheduler with all periodic tasks.
    Called once during FastAPI startup.
    """
    scheduler = get_scheduler()

    if scheduler.running:
        logger.info("[SCHEDULER] Already running, skipping start")
        return scheduler

    # --- Appointment Reminders: every hour ---
    scheduler.add_job(
        _run_reminders,
        trigger=IntervalTrigger(hours=1),
        args=[db],
        id="appointment_reminders",
        name="Hourly Appointment Reminders",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),  # Run immediately on startup
    )

    # --- Daily Summary: every day at 20:00 UTC (adjust per shop TZ if needed) ---
    summary_hour = int(os.environ.get("DAILY_SUMMARY_HOUR", "20"))
    scheduler.add_job(
        _run_daily_summary,
        trigger=CronTrigger(hour=summary_hour, minute=0),
        args=[db],
        id="daily_summary",
        name="Daily Owner Summary Email",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"[SCHEDULER] Started — reminders every 1h, daily summary at {summary_hour}:00 UTC"
    )
    return scheduler


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] Stopped")
    _scheduler = None


def get_job_status() -> list:
    """Return status of all scheduled jobs."""
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs
