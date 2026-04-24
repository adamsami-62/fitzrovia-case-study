"""Arcanos Property Management scraper base.

Arcanos runs a WordPress/CMS-style site with server-rendered HTML. However,
the Lift framework JS hydrates the DOM and hoists the inquiry form modals
(including the <input class="suite_type_id">) out of each .suite block.

What survives inside .suite after hydration:
  - .availability (class tells us available vs not-available)
  - .rate-value (monthly rent)
  - .sq-ft (square footage)
  - .type-name (display name)
  - a.floorplan-link[data-pdf] (when a PDF exists)
  - the raw <div id="modal-suite-N"> wrapper (modal body hoisted, but id stays)

We extract the suite_type_id from the "modal-suite-N" pattern in the suite's
inner HTML, which is 100% reliable for available units.

Listing granularity: floorplan_template. Only units flagged available are emitted.
"""
from __future__ import annotations

import logging
import re

from playwright.async_api import Page

from backend.app.scrapers.base import BaseScraper, normalize_unit_type
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


PROMO_KEYWORDS = [
    "free month", "months free", "one month free", "1 month free",
    "rent free", "free rent", "move-in bonus", "move in bonus",
    "special offer", "promotion", "promo", "incentive",
    "limited time", "limited-time", "waived",
]

SUITE_ID_PATTERN = re.compile(r"modal-suite-(\d+)")
PDF_BED_PATTERN = re.compile(r"_(\d+)(bed|_den)_", re.IGNORECASE)
ISO_DATE_PATTERN = re.compile(r"Available (\w+ \d+,? \d{4})")


class ArcanosBaseScraper(BaseScraper):
    """Base for Arcanos-managed properties."""

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        suites = page.locator("div.suite")
        total = await suites.count()
        log.info(f"[{self.scraper_key}] found {total} suite blocks")

        units: list[ScrapedUnit] = []
        for i in range(total):
            suite = suites.nth(i)

            avail_el = suite.locator(".availability").first
            if await avail_el.count() == 0:
                continue
            avail_class = await avail_el.get_attribute("class") or ""
            if "not-available" in avail_class:
                continue
            avail_text = (await avail_el.inner_text()).strip()

            suite_html = await suite.inner_html()
            match = SUITE_ID_PATTERN.search(suite_html)
            if not match:
                log.warning(f"[{self.scraper_key}] suite {i}: no modal-suite-N found, skipping")
                continue
            suite_id = match.group(1)

            rate_el = suite.locator(".rate-value").first
            if await rate_el.count() == 0:
                continue
            rate_text = (await rate_el.inner_text()).strip()
            rent_match = re.search(r"\$\s*([\d,]+)", rate_text)
            if not rent_match:
                log.warning(f"[{self.scraper_key}] suite {suite_id}: cannot parse rent from {rate_text!r}")
                continue
            rent = float(rent_match.group(1).replace(",", ""))

            sqft_el = suite.locator(".sq-ft").first
            sqft = None
            if await sqft_el.count() > 0:
                sqft_text = (await sqft_el.inner_text()).strip()
                sqft_match = re.search(r"(\d+)", sqft_text)
                if sqft_match:
                    sqft = int(sqft_match.group(1))

            unit_type = await self._classify_unit_type(suite, suite_id, sqft)

            available_date = None
            if "Available Now" in avail_text:
                available_date = "Available Now"
            else:
                date_match = ISO_DATE_PATTERN.search(avail_text)
                if date_match:
                    available_date = date_match.group(1)

            units.append(ScrapedUnit(
                unit_identifier=suite_id,
                unit_type=unit_type,
                rent=rent,
                sqft=sqft,
                incentive_raw=None,
                floor=None,
                available_date=available_date,
                listing_url=self.url,
                listing_type="floorplan_template",
            ))

        return units

    async def _classify_unit_type(self, suite, suite_id, sqft):
        """Subclasses may override by calling super() after their own overrides."""
        pdf_link = suite.locator("a.floorplan-link").first
        if await pdf_link.count() > 0:
            pdf_url = await pdf_link.get_attribute("data-pdf") or ""
            match = PDF_BED_PATTERN.search(pdf_url)
            if match:
                bed_count = match.group(1)
                suffix = match.group(2).lower()
                synthetic = f"{bed_count} bed{' + den' if suffix == '_den' else ''}"
                return normalize_unit_type(synthetic)
        return "unknown"

    async def extract_incentive(self, page: Page):
        desc_el = page.locator(".building-description .cms-content").first
        if await desc_el.count() == 0:
            return None
        desc = (await desc_el.inner_text()).strip()
        low = desc.lower()
        for kw in PROMO_KEYWORDS:
            if kw in low:
                log.info(f"[{self.scraper_key}] incentive keyword {kw!r} matched")
                return desc[:2000]
        return None
