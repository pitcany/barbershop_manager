"""
Celery task: daily owner summary email.

Worker entry point for run_daily_summary_for_all_shops.
Creates its own Motor client — Celery workers are separate processes
and cannot share the FastAPI app's database connection.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from celery_app import celery_app

logger = logging.getLogger(__name__)

JOB_NAME = "daily_summary"


def _get_window_key() -> str:
    """Daily idempotency window: daily_summary:YYYY-MM-DD"""
    return f"daily_summary:{datetime.utcnow().strftime('%Y-%m-%d')}"


def _build_db():
    """Create a fresh Motor async client for use inside a Celery task."""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "barbershop_autopilot")
    client = AsyncIOMotorClient(mongo_url)
    return client, client[db_name]


async def _run(window_key: str) -> dict:
    """Async core: idempotency check → business logic → run tracking."""
    client, db = _build_db()
    try:
        # --- Idempotency guard ---
        existing = await db.job_runs.find_one(
            {"job_name": JOB_NAME, "window_key": window_key, "status": "completed"},
            {"_id": 0},
        )
        if existing:
            logger.info(
                "[CELERY] %s window %s already completed — skipping",
                JOB_NAME,
                window_key,
            )
            return {"skipped": True, "window_key": window_key}

        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        # --- Write "running" record (upsert so retries don't create duplicates) ---
        await db.job_runs.update_one(
            {"job_name": JOB_NAME, "window_key": window_key},
            {
                "$setOnInsert": {"id": run_id},
                "$set": {
                    "status": "running",
                    "started_at": started_at,
                    "finished_at": None,
                    "error": None,
                    "results": None,
                },
                "$inc": {"attempt": 1},
            },
            upsert=True,
        )

        # --- Business logic ---
        from owner_ops_agent import run_daily_summary_for_all_shops

        results = await run_daily_summary_for_all_shops(db)

        finished_at = datetime.now(timezone.utc).isoformat()
        await db.job_runs.update_one(
            {"job_name": JOB_NAME, "window_key": window_key},
            {
                "$set": {
                    "status": "completed",
                    "finished_at": finished_at,
                    "results": results,
                }
            },
        )

        logger.info(
            "[CELERY] %s window %s completed: %s", JOB_NAME, window_key, results
        )
        return results

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        try:
            await db.job_runs.update_one(
                {"job_name": JOB_NAME, "window_key": window_key},
                {
                    "$set": {
                        "status": "failed",
                        "finished_at": finished_at,
                        "error": str(exc),
                    }
                },
            )
        except Exception:
            pass
        raise
    finally:
        client.close()


@celery_app.task(
    bind=True,
    name="tasks.owner_ops.run_daily_summary_task",
    max_retries=3,
    default_retry_delay=300,
)
def run_daily_summary_task(self):
    """Celery task: run daily summary email for all shops."""
    window_key = _get_window_key()
    logger.info("[CELERY] %s starting, window=%s", JOB_NAME, window_key)
    try:
        return asyncio.run(_run(window_key))
    except Exception as exc:
        logger.error("[CELERY] %s failed: %s", JOB_NAME, exc)
        raise self.retry(exc=exc)
