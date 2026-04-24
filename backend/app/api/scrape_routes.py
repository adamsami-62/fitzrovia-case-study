"""POST /scrape/trigger — admin-only live scrape of all buildings."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.schemas import ScrapeTriggerResponse
from backend.app.auth import require_admin
from backend.app.database import get_db
from backend.app.models import ScrapeRun, User
from backend.app.scrapers.registry import instantiate_all
from backend.app.scrapers.runner import run_scrapers


router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("/trigger", response_model=ScrapeTriggerResponse)
async def trigger_scrape(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Synchronously run all scrapers and return the run summary.

    This blocks for ~60-90 seconds. In a production system we'd enqueue this
    as a background task and poll for status, but for the case study the
    interviewer needs to see the live scrape happen and the fresh numbers
    appear, so blocking with a visible spinner on the frontend is correct.
    """
    t0 = time.monotonic()
    scrapers = instantiate_all()
    summary = await run_scrapers(scrapers)
    elapsed = time.monotonic() - t0

    run = db.query(ScrapeRun).filter(ScrapeRun.id == summary["run_id"]).first()
    return ScrapeTriggerResponse(
        run_id=summary["run_id"],
        status=summary["status"],
        buildings_attempted=summary["buildings_attempted"],
        buildings_succeeded=summary["buildings_succeeded"],
        total_units_found=summary["total_units_found"],
        started_at=run.started_at if run else datetime.now(timezone.utc),
        finished_at=run.finished_at if run else None,
        elapsed_seconds=round(elapsed, 2),
    )
