"""Pydantic response models for the API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_identifier: str
    unit_type: str
    rent: float
    sqft: int | None
    floor: int | None
    available_date: str | None
    listing_url: str | None
    listing_type: str
    is_currently_available: bool
    last_seen_at: datetime


class BuildingSummary(BaseModel):
    """Row-level aggregates for the dashboard."""
    id: int
    name: str
    address: str
    last_scraped_at: datetime | None
    last_scrape_status: str
    last_scrape_error: str | None
    source_url: str | None
    total_units: int
    units_by_type: dict[str, int]
    rent_min: float | None
    rent_max: float | None
    rent_avg: float | None
    has_incentive: bool
    incentive_raw: str | None
    incentive_parsed: dict[str, Any] | None
    incentive_source_url: str | None


class UnitTypeAggregate(BaseModel):
    """Cross-building roll-up for a single unit_type."""
    unit_type: str
    total_available: int
    buildings_count: int
    rent_min: float | None
    rent_max: float | None
    rent_avg: float | None
    sqft_min: int | None
    sqft_max: int | None


class DashboardResponse(BaseModel):
    generated_at: datetime
    last_run_finished_at: datetime | None
    total_units: int
    total_buildings: int
    buildings_succeeded: int
    buildings_failed: int
    buildings_with_incentives: int
    by_unit_type: list[UnitTypeAggregate]
    buildings: list[BuildingSummary]


class BuildingDetail(BuildingSummary):
    units: list[UnitOut]


class ScrapeTriggerResponse(BaseModel):
    run_id: int
    status: str
    buildings_attempted: int
    buildings_succeeded: int
    total_units_found: int
    started_at: datetime
    finished_at: datetime | None
    elapsed_seconds: float
