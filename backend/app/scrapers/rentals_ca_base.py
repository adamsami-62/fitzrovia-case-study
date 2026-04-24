"""Rentals.ca base scraper.

Rentals.ca is a Canadian listing aggregator that syndicates property data for
many management companies (including Arcanos / Fitzrovia buildings). The full
building payload is embedded in a server-side <script> tag as:

    App.store.listing = {...json...};
    App.store.availablePropertyTypes = [...];

This gives us everything in one request: the units array (with id, beds,
dimensions, rent, date_available, is_available), promotions, description,
and company metadata. No need to parse rendered DOM.

Listing granularity: specific_unit. Each element in the units[] array is a
specific bookable unit with a unique Rentals.ca id; we use that id as
unit_identifier (matches Parker/Selby pattern).

Incentive detection: checks listing["promotions"] first (authoritative).
Falls back to keyword scan of listing["description_text"] so we don't miss
promotions described inline but not in the structured field.
"""
from __future__ import annotations

import json
import logging
import re

from playwright.async_api import Page

from backend.app.scrapers.base import BaseScraper, normalize_unit_type
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


JSON_PATTERN = re.compile(
    r"App\.store\.listing\s*=\s*(\{.*?\});\s*App\.store\.availablePropertyTypes",
    re.DOTALL,
)

PROMO_KEYWORDS = [
    "free month", "months free", "one month free", "1 month free",
    "rent free", "free rent", "move-in bonus", "move in bonus",
    "special offer", "promotion", "promo", "incentive",
    "limited time", "limited-time", "waived",
]


class RentalsCaBaseScraper(BaseScraper):
    """Base class for any Rentals.ca-hosted listing."""

    # Subclass must set: name, scraper_key, url

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        html = await page.content()
        listing = self._extract_listing_json(html)
        if listing is None:
            log.error(f"[{self.scraper_key}] could not locate App.store.listing JSON")
            return []

        units_raw = listing.get("units") or []
        listing_url = listing.get("url") or self.url

        units: list[ScrapedUnit] = []
        for u in units_raw:
            rent = u.get("rent")
            if rent is None:
                log.warning(f"[{self.scraper_key}] unit {u.get('id')}: missing rent, skipping")
                continue

            unit_type_str = u.get("name") or ""
            unit_type = normalize_unit_type(unit_type_str)

            sqft_val = u.get("dimensions")
            sqft = int(sqft_val) if sqft_val else None

            avail = u.get("date_available")

            units.append(ScrapedUnit(
                unit_identifier=str(u.get("id")),
                unit_type=unit_type,
                rent=float(rent),
                sqft=sqft,
                incentive_raw=None,
                floor=None,
                available_date=avail,
                listing_url=listing_url,
                listing_type="specific_unit",
            ))

        return units

    async def extract_incentive(self, page: Page) -> str | None:
        html = await page.content()
        listing = self._extract_listing_json(html)
        if listing is None:
            return None

        promos = listing.get("promotions") or []
        if promos:
            parts: list[str] = []
            for p in promos:
                if isinstance(p, dict):
                    text = p.get("description") or p.get("title") or p.get("text") or ""
                    if text:
                        parts.append(str(text))
                elif isinstance(p, str):
                    parts.append(p)
            if parts:
                joined = " | ".join(parts)
                log.info(f"[{self.scraper_key}] incentive from promotions[]: {joined[:100]}")
                return joined[:2000]

        desc = (listing.get("description_text") or "").lower()
        for kw in PROMO_KEYWORDS:
            if kw in desc:
                full_desc = listing.get("description_text") or ""
                log.info(f"[{self.scraper_key}] incentive keyword '{kw}' matched in description")
                return full_desc[:2000]

        log.info(f"[{self.scraper_key}] no incentive found")
        return None

    @staticmethod
    def _extract_listing_json(html: str) -> dict | None:
        m = JSON_PATTERN.search(html)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as e:
            log.error(f"JSON parse failed: {e}")
            return None
