from __future__ import annotations

import logging
import threading
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from .analyzer import analyze_pending
from .config import get_settings
from .plan import generate_training_plan
from .sync import sync_games

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_job_lock = threading.Lock()
_running = False


def full_pipeline(force_sync_full: bool = False, analyze_limit: int | None = None) -> dict[str, Any]:
    global _running
    if not _job_lock.acquire(blocking=False):
        return {"status": "busy", "message": "Ein Job läuft bereits"}
    _running = True
    try:
        sync_result = sync_games(force_full=force_sync_full)
        analyze_result = analyze_pending(limit=analyze_limit)
        plan = None
        if analyze_result.get("analyzed", 0) > 0 or analyze_result.get("total_analyzed", 0) > 0:
            plan = generate_training_plan()
        return {
            "status": "ok",
            "sync": sync_result,
            "analyze": analyze_result,
            "plan_generated": plan is not None,
        }
    finally:
        _running = False
        _job_lock.release()


def analyze_pipeline(limit: int | None = None) -> dict[str, Any]:
    global _running
    if not _job_lock.acquire(blocking=False):
        return {"status": "busy", "message": "Ein Job läuft bereits"}
    _running = True
    try:
        analyze_result = analyze_pending(limit=limit)
        plan = None
        if analyze_result.get("total_analyzed", 0) > 0:
            plan = generate_training_plan()
        return {
            "status": "ok",
            "analyze": analyze_result,
            "plan_generated": plan is not None,
        }
    finally:
        _running = False
        _job_lock.release()


def scheduled_job() -> None:
    try:
        logger.info("Geplanter Sync/Analyse gestartet")
        full_pipeline()
    except Exception:
        logger.exception("Geplanter Job fehlgeschlagen")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    settings = get_settings()
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        scheduled_job,
        "interval",
        hours=settings.sync_interval_hours,
        id="sync_analyze",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler gestartet (alle %s Stunden)", settings.sync_interval_hours)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def is_job_running() -> bool:
    return _running
