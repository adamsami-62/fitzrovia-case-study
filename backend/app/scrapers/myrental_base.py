"""Rentsync Website Gateway scraper base (myrental.ca, akoyaliving.ca, etc.).

Properties managed by KG Group (and potentially other clients) on myrental.ca
expose a clean REST API via website-gateway.rentsync.com. No Playwright needed:
a single HTTP GET returns JSON with every tracked unit and its full state.

Endpoint pattern:
  https://website-gateway.rentsync.com/v1/{theme_slug}/unit-table-builder
    ?where=propertyId~in:{propertyId},type~in:columns,showUnavailableUnits~in:true

The response includes data.units[], where each unit has:
  - typeName     : floorplan name (Addison, Bedford, etc.)
  - number       : unit number
  - bed, bath    : bedroom and bathroom counts
  - den          : "yes" | "no" (+ den variants roll up to base bedroom count)
  - sqFt, rate   : as strings
  - floor        : floor number
  - available    : -1 (waitlist) | 0 (unavailable) | 1 (available)
  - availabilityDate : ISO date string or null

Availability encoding for available_date (matches Hampton convention):
  - available: -1                              -> "Waitlist"
  - available:  1 + future availabilityDate    -> "Mon D, YYYY"
  - available:  1 + null availabilityDate      -> "Available Now"
  - available:  0                              -> "Unavailable"

Listing granularity: specific_unit (API gives real unit numbers, not templates).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx

from backend.app.scrapers.base import BaseScraper, normalize_unit_type
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


GATEWAY_BASE = "https://website-gateway.rentsync.com/v1"
MYRENTAL_BASE = "https://www.myrental.ca/apartments-for-rent"

# Promo banner lives in <div id="rdPromotionBanner"> ... <h2>TEXT</h2>.
# Pull the h2 text directly with a non-greedy DOTALL match.
PROMO_BANNER_PATTERN = re.compile(
    r'id="rdPromotionBanner".*?<h2[^>]*>\s*([^<]+?)\s*</h2>',
    re.DOTALL | re.IGNORECASE,
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def _format_date(iso_date: str) -> str:
    """Convert '2026-06-01' to 'Jun 1, 2026' to match Hampton's convention."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%b %-d, %Y")
    except (ValueError, TypeError):
        return iso_date


def _derive_availability(unit: dict) -> str | None:
    available = unit.get("available")
    avail_date = unit.get("availabilityDate")

    if available == -1:
        return "Waitlist"
    if available == 0:
        return "Unavailable"
    if available == 1:
        if avail_date:
            return _format_date(avail_date)
        return "Available Now"
    return None


def _derive_unit_type(unit: dict) -> str:
    bed = unit.get("bed")
    if bed is None:
        return "unknown"
    if bed == 0:
        return "bachelor"
    den_suffix = " + den" if str(unit.get("den", "no")).lower() == "yes" else ""
    return normalize_unit_type(f"{bed} bed{den_suffix}")


class MyRentalBaseScraper(BaseScraper):
    """Base for properties on myrental.ca / rentsync website-gateway."""

    # Subclasses must set:
    property_id: int = 0
    theme_slug: str = "kg_rebuild"
    permalink: str = ""  # e.g. "18-erskine-ave" for the public-facing page

    # Gateway query behavior. E18HTEEN wants unavailable units included (to detect
    # waitlist state); Akoya wants only available ones (matches its site behavior).
    show_unavailable_units: bool = True

    # "specific_unit" when the gateway returns per-unit rows (E18HTEEN, unit 406 etc.)
    # "floorplan_template" when it returns per-floorplan summaries (Akoya, Lotus I etc.)
    listing_granularity: str = "specific_unit"

    # Public-facing site base. Defaults to myrental.ca (KG Group). Akoya overrides.
    site_base: str = "https://www.myrental.ca/apartments-for-rent"

    # Class-level URL is set in __init__ from property_id so runner/persist see it.
    url: str = ""

    def __init__(self):
        super().__init__()
        self.url = self._api_url()

    def _api_url(self) -> str:
        return (
            f"{GATEWAY_BASE}/{self.theme_slug}/unit-table-builder"
            f"?where=propertyId~in:{self.property_id}"
            f",type~in:columns,showUnavailableUnits~in:{str(self.show_unavailable_units).lower()}"
        )

    async def run(self) -> ScrapeResult:
        result = ScrapeResult(
            building_name=self.name,
            scraper_key=self.scraper_key,
            status="failed",
            units=[],
            source_url=self.url,
        )
        try:
            log.info(f"[{self.scraper_key}] fetching {self.url}")
            async with httpx.AsyncClient(
                timeout=20.0,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            ) as client:
                resp = await client.get(self.url)
                resp.raise_for_status()
                payload = resp.json()

            units_raw = payload.get("data", {}).get("units", [])
            log.info(f"[{self.scraper_key}] received {len(units_raw)} units")

            units: list[ScrapedUnit] = []
            for u in units_raw:
                number = str(u.get("number") or "").strip()
                type_name = str(u.get("typeName") or "").strip()
                # For floorplan_template scrapers, unit "number" is blank — fall back to typeName.
                unit_identifier = number or type_name
                if not unit_identifier:
                    log.warning(f"[{self.scraper_key}] unit {u.get('id')}: no number or typeName, skipping")
                    continue

                try:
                    rent = float(str(u.get("rate") or "0").replace(",", ""))
                except ValueError:
                    log.warning(f"[{self.scraper_key}] unit {number}: bad rent {u.get('rate')!r}, skipping")
                    continue
                if rent <= 0:
                    continue

                try:
                    sqft = int(str(u.get("sqFt") or "").replace(",", "")) or None
                except ValueError:
                    sqft = None

                floor = str(u.get("floor") or "").strip() or None
                unit_type = _derive_unit_type(u)
                available_date = _derive_availability(u)

                units.append(ScrapedUnit(
                    unit_identifier=unit_identifier,
                    unit_type=unit_type,
                    rent=rent,
                    sqft=sqft,
                    incentive_raw=None,
                    floor=floor,
                    available_date=available_date,
                    listing_url=self.url,
                    listing_type=self.listing_granularity,
                ))

            result.units = units
            result.status = "success"

            # Hook for subclasses to customize incentive scraping.
            try:
                incentive = await self._fetch_incentive()
                if incentive is not None:
                    banner_text, banner_url = incentive
                    result.incentive_raw = banner_text
                    result.incentive_source_url = banner_url
                    log.info(f"[{self.scraper_key}] incentive banner: {banner_text[:100]}...")
            except Exception as e:
                log.warning(f"[{self.scraper_key}] banner fetch failed: {e}")

            return result

        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            log.error(f"[{self.scraper_key}] {result.error}")
            return result
        except httpx.RequestError as e:
            result.error = f"Request error: {e!r}"
            log.error(f"[{self.scraper_key}] {result.error}")
            return result
        except Exception as e:
            result.error = f"Unexpected: {e!r}"
            log.error(f"[{self.scraper_key}] {result.error}")
            return result

    async def _fetch_incentive(self) -> tuple[str, str] | None:
        """Fetch the incentive banner. Default: myrental.ca #rdPromotionBanner pattern.

        Returns (banner_text, banner_url) if found, else None. Subclasses override
        for site-specific banner logic (e.g. Akoya's multi-promo modal on the homepage).
        """
        if not self.permalink:
            return None
        banner_url = f"{self.site_base}/{self.permalink}"
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            follow_redirects=True,
        ) as html_client:
            html_resp = await html_client.get(banner_url)
            html_resp.raise_for_status()
            match = PROMO_BANNER_PATTERN.search(html_resp.text)
            if match:
                return (match.group(1).strip(), banner_url)
        return None

    # Not used (run() overridden) but required by abstract base.
    async def extract_units(self, page):
        raise NotImplementedError("MyRentalBase uses run() directly; extract_units not called.")
