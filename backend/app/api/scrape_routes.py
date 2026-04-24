"""Scrape endpoints.

POST /scrape/trigger       kicks off a scrape in the background (admin only), returns run_id.
GET  /scrape/runs/{run_id} returns current status, polled by the frontend.

Background execution is done via asyncio.create_task, which lives on the server's event loop
for the lifetime of the process. Render free tier is single-worker so this is fine; a real
deployment with multiple workers would need a shared queue (Redis + RQ, Celery, etc.).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.schemas import ScrapeKickoffResponse, ScrapeRunStatus
from backend.app.auth import require_admin, get_current_user
from backend.app.database import SessionLocal, get_db
from backend.app.models import ScrapeRun, User
from backend.app.scrapers.registry import instantiate_all
from backend.app.scrapers.runner import run_scrapers


log = logging.getLogger(__name__)

router = APIRouter(prefix="/scrape", tags=["scrape"])


# Track running tasks by run_id. Lets us prevent overlapping scrapes and tell the
# frontend "still running" vs "finished." Process-local, fine for single-worker setups.
_running_tasks: dict[int, asyncio.Task] = {}


async def _do_scrape(run_id_promise: asyncio.Future) -> None:
    """Run all scrapers, then resolve the promise with the run_id so the HTTP
    handler can return it before the scrape finishes."""
    scrapers = instantiate_all()

    # run_scrapers creates the ScrapeRun row itself, so the run_id we return is the one
    # it assigns. Easiest way to get it: wrap in a coroutine that publishes the id as
    # soon as it is assigned. Simplest approach — let run_scrapers create the row, then
    # fish the id back out via the returned summary.
    t0 = time.monotonic()
    try:
        summary = await run_scrapers(scrapers)
        log.info(f"Background scrape finished: run_id={summary['run_id']} in {time.monotonic() - t0:.1f}s")
        if not run_id_promise.done():
            run_id_promise.set_result(summary["run_id"])
    except Exception as e:
        log.exception("Background scrape failed")
        if not run_id_promise.done():
            run_id_promise.set_exception(e)


@router.post("/trigger", response_model=ScrapeKickoffResponse)
async def trigger_scrape(
    _: User = Depends(require_admin),
):
    """Kick off a scrape in the background. Return immediately with a run_id.

    The frontend polls GET /scrape/runs/{run_id} to track progress.
    """
    # Don't allow overlapping scrapes. If one is already running, return its run_id.
    for rid, task in list(_running_tasks.items()):
        if not task.done():
            return ScrapeKickoffResponse(
                run_id=rid,
                status="running",
                message=f"A scrape is already in progress (run {rid}). Polling that one.",
            )
        else:
            _running_tasks.pop(rid, None)

    # Create the ScrapeRun row up front so we can return its id immediately.
    db = SessionLocal()
    try:
        run = ScrapeRun(
            started_at=datetime.now(timezone.utc),
            status="running",
            buildings_attempted=len(instantiate_all()),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    finally:
        db.close()

    # Kick off the work in the background. We pass run_id so the task knows which
    # row to update. run_scrapers currently creates its own row — we'll wrap it
    # so that it uses the existing row instead.
    task = asyncio.create_task(_run_scrape_into_existing_row(run_id))
    _running_tasks[run_id] = task

    return ScrapeKickoffResponse(
        run_id=run_id,
        status="running",
        message=f"Scrape {run_id} started. Poll /scrape/runs/{run_id} for progress.",
    )


async def _run_scrape_into_existing_row(run_id: int) -> None:
    """Run all scrapers and update the existing ScrapeRun row with the result.

    Mirrors run_scrapers' body but uses a pre-existing run_id rather than creating a new row.
    Keeps all the real logic in one place — this is a thin wrapper so the HTTP handler can
    return before the scrape finishes.
    """
    from backend.app.scrapers.persist import persist_result

    scrapers = instantiate_all()
    db = SessionLocal()
    try:
        run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
        if run is None:
            log.error(f"run_id {run_id} disappeared before scrape could start")
            return

        t0 = time.monotonic()
        try:
            results = await asyncio.gather(
                *(s.run() for s in scrapers),
                return_exceptions=False,
            )
        except Exception as e:
            log.exception(f"run {run_id} failed catastrophically")
            run.finished_at = datetime.now(timezone.utc)
            run.status = "failed"
            run.error_message = f"{type(e).__name__}: {e}"
            db.commit()
            return

        succeeded = 0
        total_units = 0
        for result in results:
            summary = persist_result(db, run, result)
            if summary.get("status") == "success":
                succeeded += 1
                total_units += summary.get("units", 0)

        run.finished_at = datetime.now(timezone.utc)
        run.buildings_succeeded = succeeded
        run.total_units_found = total_units
        if succeeded == len(scrapers):
            run.status = "success"
        elif succeeded == 0:
            run.status = "failed"
        else:
            run.status = "partial"
        db.commit()
        log.info(f"run {run_id} finished: {run.status}, {succeeded}/{len(scrapers)} buildings, {total_units} units, {time.monotonic() - t0:.1f}s")
    finally:
        db.close()


@router.get("/runs/{run_id}", response_model=ScrapeRunStatus)
def get_run_status(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return current status of a scrape run. Polled by the frontend."""
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    is_complete = run.finished_at is not None
    elapsed = (
        (run.finished_at - run.started_at).total_seconds()
        if run.finished_at
        else (datetime.now(timezone.utc) - run.started_at.replace(tzinfo=timezone.utc)).total_seconds()
    )
    buildings_failed = max(0, run.buildings_attempted - run.buildings_succeeded) if is_complete else 0

    return ScrapeRunStatus(
        run_id=run.id,
        status=run.status,
        buildings_attempted=run.buildings_attempted,
        buildings_succeeded=run.buildings_succeeded,
        buildings_failed=buildings_failed,
        total_units_found=run.total_units_found,
        started_at=run.started_at,
        finished_at=run.finished_at,
        elapsed_seconds=round(elapsed, 1),
        is_complete=is_complete,
    )
