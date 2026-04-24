"""Take a ScrapeResult and write it to the database."""
import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.ai.incentive_parser import parse_incentive
from backend.app.models import Building, ScrapeRun, ScrapeSnapshot, Unit
from backend.app.scrapers.schema import ScrapeResult


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def persist_result(db: Session, run: ScrapeRun, result: ScrapeResult) -> dict:
    building = db.query(Building).filter_by(scraper_key=result.scraper_key).first()
    if building is None:
        return {"error": f"No building row found for scraper_key={result.scraper_key}"}

    building.last_scraped_at = datetime.utcnow()
    building.last_scrape_status = result.status
    building.last_scrape_error = result.error
    if result.source_url:
        building.source_url = result.source_url

    if result.status != "success":
        db.commit()
        return {"building": building.name, "status": "failed", "units": 0}

    # Incentive handling with change detection.
    # If parse_incentive returns _ok=False, we DO store the raw text and the
    # fallback parse result (so the dashboard can surface the error), but we do
    # NOT update incentive_hash. That way the next scrape sees the hash as
    # stale and retries the parse — auto-healing against transient API errors.
    incentive_ai_called = False
    if result.incentive_raw:
        new_hash = _hash_text(result.incentive_raw)
        if building.incentive_hash != new_hash:
            parsed = parse_incentive(result.incentive_raw)
            building.current_incentive_raw = result.incentive_raw
            building.current_incentive_parsed = parsed
            if parsed and parsed.get("_ok"):
                building.incentive_hash = new_hash
            incentive_ai_called = True
        building.incentive_last_seen_at = datetime.utcnow()
        building.incentive_source_url = result.incentive_source_url
    else:
        if building.current_incentive_raw is not None:
            building.current_incentive_raw = None
            building.current_incentive_parsed = None
            building.incentive_hash = None

    # Units upsert
    now = datetime.utcnow()
    seen_identifiers = set()

    for scraped in result.units:
        seen_identifiers.add(scraped.unit_identifier)
        # For specific-unit scrapers, null availability means the site listed the
        # unit without a concrete date. We treat that as available now, since the
        # site itself considers it leasable. Floorplan-template scrapers
        # (Whitney, Corner, Akoya) keep null because they genuinely don't expose
        # per-unit availability.
        if (
            scraped.listing_type == "specific_unit"
            and not scraped.available_date
        ):
            scraped.available_date = "Available Now"
        existing = (
            db.query(Unit)
            .filter_by(building_id=building.id, unit_identifier=scraped.unit_identifier)
            .first()
        )
        if existing is None:
            db.add(Unit(
                building_id=building.id,
                unit_identifier=scraped.unit_identifier,
                unit_type=scraped.unit_type,
                rent=scraped.rent,
                sqft=scraped.sqft,
                incentive_raw=scraped.incentive_raw,
                floor=scraped.floor,
                available_date=scraped.available_date,
                listing_url=scraped.listing_url,
                listing_type=scraped.listing_type,
                is_currently_available=True,
                first_seen_at=now,
                last_seen_at=now,
            ))
        else:
            existing.unit_type = scraped.unit_type
            existing.rent = scraped.rent
            existing.sqft = scraped.sqft
            existing.incentive_raw = scraped.incentive_raw
            existing.floor = scraped.floor
            existing.available_date = scraped.available_date
            existing.listing_url = scraped.listing_url
            existing.listing_type = scraped.listing_type
            existing.is_currently_available = True
            existing.last_seen_at = now

        db.add(ScrapeSnapshot(
            run_id=run.id,
            building_id=building.id,
            unit_identifier=scraped.unit_identifier,
            unit_type=scraped.unit_type,
            rent=scraped.rent,
            sqft=scraped.sqft,
            incentive_raw=scraped.incentive_raw,
            scraped_at=now,
        ))

    # Mark previously-seen units not in this scrape as unavailable
    if seen_identifiers:
        stale_units = (
            db.query(Unit)
            .filter(Unit.building_id == building.id,
                    Unit.is_currently_available == True,
                    ~Unit.unit_identifier.in_(seen_identifiers))
            .all()
        )
    else:
        stale_units = []
    for u in stale_units:
        u.is_currently_available = False

    db.commit()

    return {
        "building": building.name,
        "status": "success",
        "units": len(result.units),
        "newly_unavailable": len(stale_units),
        "incentive_found": result.incentive_raw is not None,
        "incentive_ai_called": incentive_ai_called,
    }
