"""Run multiple scrapers concurrently and persist all results under one ScrapeRun."""
import asyncio
from datetime import datetime

from backend.app.database import SessionLocal
from backend.app.models import ScrapeRun
from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.persist import persist_result


async def run_scrapers(scrapers: list[BaseScraper]) -> dict:
    """Launch all scrapers in parallel, persist results, return a summary."""
    db = SessionLocal()
    try:
        run = ScrapeRun(started_at=datetime.utcnow(), status="running",
                        buildings_attempted=len(scrapers))
        db.add(run)
        db.commit()
        db.refresh(run)

        # Launch all scrapers concurrently
        results = await asyncio.gather(
            *(s.run() for s in scrapers),
            return_exceptions=False,  # base class already wraps exceptions
        )

        summaries = []
        succeeded = 0
        total_units = 0
        for result in results:
            summary = persist_result(db, run, result)
            summaries.append(summary)
            if summary.get("status") == "success":
                succeeded += 1
                total_units += summary.get("units", 0)

        # Finalize the run
        run.finished_at = datetime.utcnow()
        run.buildings_succeeded = succeeded
        run.total_units_found = total_units
        if succeeded == len(scrapers):
            run.status = "success"
        elif succeeded == 0:
            run.status = "failed"
        else:
            run.status = "partial"
        db.commit()

        return {
            "run_id": run.id,
            "status": run.status,
            "buildings_attempted": run.buildings_attempted,
            "buildings_succeeded": succeeded,
            "total_units_found": total_units,
            "per_building": summaries,
        }
    finally:
        db.close()
