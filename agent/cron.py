"""Cron jobs — tâches récurrentes autonomes, style OpenClaw."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from core.log import log

_CRON_FILE = Path(__file__).resolve().parent.parent / "cron_jobs.json"
_jobs: list[dict] = []
_running = False


def _load_jobs():
    global _jobs
    if _CRON_FILE.exists():
        _jobs = json.loads(_CRON_FILE.read_text())
        log.info(f"Loaded {len(_jobs)} cron jobs")
    else:
        _jobs = []


def _save_jobs():
    _CRON_FILE.write_text(json.dumps(_jobs, indent=2, default=str))


def add_job(
    name: str,
    instruction: str,
    interval_minutes: int = 60,
    enabled: bool = True,
) -> dict:
    """Add a recurring job."""
    job = {
        "name": name,
        "instruction": instruction,
        "interval_minutes": interval_minutes,
        "enabled": enabled,
        "last_run": None,
        "next_run": datetime.utcnow().isoformat(),
        "run_count": 0,
    }
    _jobs.append(job)
    _save_jobs()
    log.info(f"Cron job added: {name} (every {interval_minutes}m)")
    return job


def remove_job(name: str) -> bool:
    global _jobs
    before = len(_jobs)
    _jobs = [j for j in _jobs if j["name"] != name]
    if len(_jobs) < before:
        _save_jobs()
        log.info(f"Cron job removed: {name}")
        return True
    return False


def list_jobs() -> list[dict]:
    return _jobs.copy()


def toggle_job(name: str, enabled: bool) -> bool:
    for job in _jobs:
        if job["name"] == name:
            job["enabled"] = enabled
            _save_jobs()
            return True
    return False


async def run_cron_loop(stop_event: asyncio.Event):
    """Background loop that checks and executes cron jobs."""
    global _running
    _load_jobs()
    _running = True

    # Lazy import to avoid circular deps
    from agent.loop import submit_task

    log.info(f"Cron scheduler started ({len(_jobs)} jobs)")

    while not stop_event.is_set():
        now = datetime.utcnow()

        for job in _jobs:
            if not job["enabled"]:
                continue

            next_run = datetime.fromisoformat(job["next_run"]) if job["next_run"] else now
            if now >= next_run:
                log.info(f"Cron firing: {job['name']}")
                try:
                    await submit_task(
                        instruction=job["instruction"],
                        source=f"cron:{job['name']}",
                    )
                except Exception as e:
                    log.error(f"Cron job {job['name']} failed to submit: {e}")

                job["last_run"] = now.isoformat()
                job["next_run"] = (now + timedelta(minutes=job["interval_minutes"])).isoformat()
                job["run_count"] += 1
                _save_jobs()

        # Check every 30 seconds
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
            break
        except asyncio.TimeoutError:
            pass

    _running = False
    log.info("Cron scheduler stopped")
