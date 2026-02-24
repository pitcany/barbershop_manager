"""
Celery application factory for Barbershop Autopilot.
Activated only when USE_CELERY_SCHEDULER=true.

Start commands:
  Worker: celery -A celery_app worker --loglevel=info
  Beat:   celery -A celery_app beat --loglevel=info
"""

import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DAILY_SUMMARY_HOUR = int(os.environ.get("DAILY_SUMMARY_HOUR", "20"))
RETENTION_SWEEP_HOUR = int(os.environ.get("RETENTION_SWEEP_HOUR", "14"))

celery_app = Celery(
    "barbershop_autopilot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "tasks.reminders",
        "tasks.owner_ops",
        "tasks.retention",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Retry policy: exponential backoff via countdown override in tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat schedule
    beat_schedule={
        "appointment-reminders-hourly": {
            "task": "tasks.reminders.run_reminders_task",
            "schedule": crontab(minute=0),  # top of every hour
        },
        "daily-summary": {
            "task": "tasks.owner_ops.run_daily_summary_task",
            "schedule": crontab(hour=DAILY_SUMMARY_HOUR, minute=0),
        },
        "retention-sweep": {
            "task": "tasks.retention.run_retention_task",
            "schedule": crontab(hour=RETENTION_SWEEP_HOUR, minute=0),
        },
    },
)
