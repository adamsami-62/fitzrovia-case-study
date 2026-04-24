"""The Hampton — 101 Roehampton Avenue, Toronto. Fitzrovia property managed
by Arcanos. Dual-source scrape:
  - arcanos.ca/rentals/the-hampton  : unit data (13 available units)
  - thehampton.ca                   : dedicated marketing site with incentive

Unit-type classification priority:
  1. Hardcoded suite_type_id overrides for the 5 units with no floorplan PDF.
     Sqft alone is unreliable: a 747 sqft 2-bed (Cottonwood) is smaller than
     an 884 sqft 1-bed+den (Hawthorn).
  2. Fall through to base class: PDF filename parse.
"""
from __future__ import annotations

import logging

from playwright.async_api import async_playwright, Browser

from backend.app.scrapers.arcanos_base import ArcanosBaseScraper, PROMO_KEYWORDS
from backend.app.scrapers.schema import ScrapeResult

log = logging.getLogger(__name__)


HAMPTON_INCENTIVE_URL = "https://thehampton.ca/"

HAMPTON_UNIT_TYPE_OVERRIDES = {
    "1469460": "1-bed",   # Birch
    "1472668": "1-bed",   # Spruce
    "1519887": "1-bed",   # Hemlock
    "1469461": "2-bed",   # Cottonwood
    "1520793": "3-bed",   # Ash
}

HAMPTON_BANNER_PHRASES = [
    "sign a lease",
    "months free",
    "move in bonus",
    "move-in bonus",
    "lease by",
]


class TheHamptonScraper(ArcanosBaseScraper):
    name = "The Hampton"
    scraper_key = "the_hampton"
    url = "https://www.arcanos.ca/rentals/the-hampton"

    async def _classify_unit_type(self, suite, suite_id, sqft):
        if suite_id in HAMPTON_UNIT_TYPE_OVERRIDES:
            return HAMPTON_UNIT_TYPE_OVERRIDES[suite_id]
        return await super()._classify_unit_type(suite, suite_id, sqft)

    async def run(self) -> ScrapeResult:
        base_result = await super().run()
        if base_result.status != "success":
            return base_result

        async with async_playwright() as pw:
            browser: Browser | None = None
            try:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1440, "height": 900},
                )
                page = await context.new_page()
                log.info(f"[{self.scraper_key}] fetching incentive: {HAMPTON_INCENTIVE_URL}")
                await page.goto(HAMPTON_INCENTIVE_URL,
                                timeout=self.page_load_timeout_ms,
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(self.post_load_wait_ms)

                incentive_text = await self._scan_for_incentive(page)
                if incentive_text:
                    base_result.incentive_raw = incentive_text
                    base_result.incentive_source_url = HAMPTON_INCENTIVE_URL
                    log.info(f"[{self.scraper_key}] incentive captured")
                else:
                    log.info(f"[{self.scraper_key}] no incentive banner found")
            except Exception as e:
                log.warning(f"[{self.scraper_key}] incentive fetch failed: {e}")
            finally:
                if browser is not None:
                    await browser.close()

        return base_result

    async def _scan_for_incentive(self, page):
        body_text = await page.locator("body").inner_text()
        low = body_text.lower()

        for phrase in HAMPTON_BANNER_PHRASES:
            idx = low.find(phrase)
            if idx == -1:
                continue
            start = max(0, idx - 200)
            end = min(len(body_text), idx + 300)
            chunk = body_text[start:end]
            sentences = chunk.replace("\n", " ").split(".")
            for sentence in sentences:
                if phrase in sentence.lower():
                    cleaned = sentence.strip()
                    if len(cleaned) > 20:
                        return cleaned[:500]

        for kw in PROMO_KEYWORDS:
            if kw in low:
                idx = low.find(kw)
                start = max(0, idx - 100)
                end = min(len(body_text), idx + 200)
                chunk = body_text[start:end].strip()
                if len(chunk) > 20:
                    return chunk[:500]

        return None
