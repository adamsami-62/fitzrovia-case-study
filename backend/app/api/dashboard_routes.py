"""GET /dashboard — roll-up view. GET /buildings/{id} — drill-down."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.schemas import (
    BuildingDetail,
    BuildingSummary,
    DashboardResponse,
    UnitOut,
    UnitTypeAggregate,
)
from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import Building, ScrapeRun, Unit, User


router = APIRouter(tags=["data"])


def _summarize_building(b: Building, units: list[Unit]) -> BuildingSummary:
    rents = [u.rent for u in units if u.rent]
    by_type = Counter(u.unit_type for u in units)
    return BuildingSummary(
        id=b.id,
        name=b.name,
        address=b.address,
        last_scraped_at=b.last_scraped_at,
        last_scrape_status=b.last_scrape_status,
        last_scrape_error=b.last_scrape_error,
        source_url=b.source_url,
        total_units=len(units),
        units_by_type=dict(by_type),
        rent_min=min(rents) if rents else None,
        rent_max=max(rents) if rents else None,
        rent_avg=round(sum(rents) / len(rents), 2) if rents else None,
        has_incentive=b.current_incentive_raw is not None,
        incentive_raw=b.current_incentive_raw,
        incentive_parsed=b.current_incentive_parsed,
        incentive_source_url=b.incentive_source_url,
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    buildings = db.query(Building).order_by(Building.name).all()

    # Gather available units in one pass per building (low-cardinality fanout is fine).
    building_units: dict[int, list[Unit]] = {}
    for b in buildings:
        building_units[b.id] = [u for u in b.units if u.is_currently_available]

    # Per-unit-type roll-up across every building.
    by_type_units: dict[str, list[Unit]] = defaultdict(list)
    by_type_buildings: dict[str, set[int]] = defaultdict(set)
    for b in buildings:
        for u in building_units[b.id]:
            by_type_units[u.unit_type].append(u)
            by_type_buildings[u.unit_type].add(b.id)

    by_unit_type: list[UnitTypeAggregate] = []
    for unit_type in sorted(by_type_units.keys()):
        us = by_type_units[unit_type]
        rents = [u.rent for u in us if u.rent]
        sqfts = [u.sqft for u in us if u.sqft]
        by_unit_type.append(UnitTypeAggregate(
            unit_type=unit_type,
            total_available=len(us),
            buildings_count=len(by_type_buildings[unit_type]),
            rent_min=min(rents) if rents else None,
            rent_max=max(rents) if rents else None,
            rent_avg=round(sum(rents) / len(rents), 2) if rents else None,
            sqft_min=min(sqfts) if sqfts else None,
            sqft_max=max(sqfts) if sqfts else None,
        ))

    summaries = [_summarize_building(b, building_units[b.id]) for b in buildings]

    last_run = (
        db.query(ScrapeRun)
        .filter(ScrapeRun.finished_at.isnot(None))
        .order_by(ScrapeRun.finished_at.desc())
        .first()
    )

    return DashboardResponse(
        generated_at=datetime.now(timezone.utc),
        last_run_finished_at=last_run.finished_at if last_run else None,
        total_units=sum(s.total_units for s in summaries),
        total_buildings=len(buildings),
        buildings_succeeded=sum(1 for s in summaries if s.last_scrape_status == "success"),
        buildings_failed=sum(1 for s in summaries if s.last_scrape_status == "failed"),
        buildings_with_incentives=sum(1 for s in summaries if s.has_incentive),
        by_unit_type=by_unit_type,
        buildings=summaries,
    )


@router.get("/buildings/{building_id}", response_model=BuildingDetail)
def get_building(
    building_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    b = db.query(Building).filter(Building.id == building_id).first()
    if b is None:
        raise HTTPException(status_code=404, detail="Building not found")

    available = [u for u in b.units if u.is_currently_available]
    # Stable ordering: by unit_type, then rent asc, then identifier.
    available.sort(key=lambda u: (u.unit_type, u.rent or 0, u.unit_identifier))

    summary = _summarize_building(b, available)
    return BuildingDetail(
        **summary.model_dump(),
        units=[UnitOut.model_validate(u) for u in available],
    )
