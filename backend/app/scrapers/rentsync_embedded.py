"""RentSync embedded-JSON scraper (Parker style)."""
from __future__ import annotations

import json
import re
from playwright.async_api import Page

from backend.app.scrapers.rentsync_base import (
    RentSyncBaseScraper, unit_type_from_bed_count,
)
from backend.app.scrapers.schema import ScrapedUnit


_DATA_DIV_RE = re.compile(
    r"""<div\s+id=["']units_details_data["']\s+data-json=['"](.*?)['"]\s*>""",
    re.DOTALL,
)


def _safe_float(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _safe_int(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


class RentSyncEmbeddedScraper(RentSyncBaseScraper):
    """For sites that embed units_details_data JSON on the floorplans page."""

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        html = await page.content()
        match = _DATA_DIV_RE.search(html)
        if not match:
            raise RuntimeError(
                f"[{self.scraper_key}] #units_details_data not on page "
                "(not a Parker-style RentSync site?)"
            )

        raw = (
            match.group(1)
            .replace("&quot;", '"')
            .replace("&amp;", "&")
            .replace("&#39;", "'")
        )
        data = json.loads(raw)

        units: list[ScrapedUnit] = []
        for floorplan_key, floorplan in data.items():
            for unit_num, u in floorplan.get("units", {}).items():
                if str(u.get("available", "0")) != "1":
                    continue
                rent = _safe_float(u.get("rate"))
                if rent is None:
                    continue
                bed = _safe_int(u.get("bed")) or 0
                avail_date = u.get("availability_date") or ""
                available_date = (
                    avail_date if avail_date and avail_date != "0000-00-00" else None
                )
                units.append(ScrapedUnit(
                    unit_identifier=u.get("number") or unit_num,
                    unit_type=unit_type_from_bed_count(bed),
                    rent=rent,
                    sqft=_safe_int(u.get("sq_ft")),
                    incentive_raw=None,
                    floor=_safe_int(u.get("floor")),
                    available_date=available_date,
                    listing_url=self.url,
                    listing_type="specific_unit",
                ))
        return units
