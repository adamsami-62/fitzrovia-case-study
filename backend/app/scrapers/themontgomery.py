"""The Montgomery — 25 Montgomery Avenue, Toronto.

Blocked by Cloudflare's JS challenge tier. Both headless Playwright and
Playwright + playwright-stealth get served the 31KB "Just a moment..."
challenge page instead of content.

Returns status='failed' with a documented error. The runner persists
this cleanly, and the dashboard flags the building as unscrapable.

See README for the remediation options considered.
"""
from __future__ import annotations

from playwright.async_api import Page

from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit


class TheMontgomeryScraper(BaseScraper):
    name = "The Montgomery"
    scraper_key = "the_montgomery"
    url = "https://www.themontgomery.ca/floorplans"

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        raise NotImplementedError("Blocked by Cloudflare; run() short-circuits")

    async def run(self) -> ScrapeResult:
        return ScrapeResult(
            building_name=self.name,
            scraper_key=self.scraper_key,
            status="failed",
            units=[],
            source_url=self.url,
            error=(
                "Cloudflare bot challenge (escalated 'Just a moment...' tier). "
                "Requires residential proxy or commercial scraping service."
            ),
        )
