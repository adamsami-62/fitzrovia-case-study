"""Canonical shape of what every scraper returns."""
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ScrapedUnit:
    unit_identifier: str
    unit_type: str
    rent: float
    sqft: int | None = None
    incentive_raw: str | None = None
    floor: int | None = None
    available_date: str | None = None
    listing_url: str | None = None
    listing_type: str = "specific_unit"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScrapeResult:
    building_name: str
    scraper_key: str
    status: str
    units: list[ScrapedUnit] = field(default_factory=list)
    error: str | None = None
    source_url: str | None = None
    incentive_raw: str | None = None
    incentive_source_url: str | None = None

    @property
    def unit_count(self) -> int:
        return len(self.units)
