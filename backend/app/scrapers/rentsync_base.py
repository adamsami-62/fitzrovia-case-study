"""Shared base for RentSync-powered scrapers.

There are (at least) two RentSync UI styles in the wild:

  - Embedded-JSON style (Parker, older sites)
    Unit inventory is baked into the floorplans page as a JSON blob on a
    hidden div (#units_details_data). Fast + reliable; no JS wait needed.

  - Navigator-widget style (Story of Midtown, newer Hazelview sites)
    Unit inventory is rendered client-side by a <floorplan-navigator>
    web component into .unit-card DOM nodes. Requires waiting for JS.

Both styles share browser setup, the two-page flow (floorplans page for
units + home page for incentives), and the incentive selector logic.
All that lives here. Style-specific extraction lives in subclasses.
"""
from __future__ import annotations

import logging
from playwright.async_api import async_playwright, Browser, Page

from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


# Selector pairs for incentive modals. We try each (container, title, body, disclaimer) set in order.
# Add new patterns here as we encounter new RentSync site variants.
INCENTIVE_SELECTORS = [
    {
        "container": "#home-popup",                      # Parker-style
        "title":     ".promo-title",
        "body":      ".cms-content",
        "disclaimer": ".cms-content.disclaimer",
    },
    {
        "container": "#promotionsModal",                 # Story of Midtown-style
        "title":     ".promotion-slide__heading",
        "body":      ".promotion-slide__content",
        "disclaimer": None,
    },
]


def unit_type_from_bed_count(bed_count: int) -> str:
    """0 -> bachelor, 1 -> 1-bed, etc."""
    if bed_count <= 0:
        return "bachelor"
    if bed_count == 1:
        return "1-bed"
    if bed_count == 2:
        return "2-bed"
    if bed_count == 3:
        return "3-bed"
    return "unknown"


class RentSyncBaseScraper(BaseScraper):
    """Shared behaviour: browser setup, two-page flow, incentive extraction.

    Subclasses must implement:
        extract_units(page) -> list[ScrapedUnit]

    Optional:
        home_url             — if set, incentive is scraped from the home page
    """
    home_url: str | None = None

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        raise NotImplementedError("Subclasses implement extract_units()")

    async def extract_incentive(self, page: Page) -> str | None:
        """Try each known incentive selector set in order. Return first match."""
        for selectors in INCENTIVE_SELECTORS:
            try:
                container = page.locator(selectors["container"]).first
                if await container.count() == 0:
                    continue

                parts: list[str] = []

                title_el = container.locator(selectors["title"]).first
                if await title_el.count() > 0:
                    t = (await title_el.inner_text()).strip()
                    if t:
                        parts.append(t)

                body_el = container.locator(selectors["body"]).first
                if await body_el.count() > 0:
                    b = (await body_el.inner_text()).strip()
                    if b:
                        parts.append(b)

                if selectors.get("disclaimer"):
                    disc_el = container.locator(selectors["disclaimer"]).first
                    if await disc_el.count() > 0:
                        d = (await disc_el.inner_text()).strip()
                        if d:
                            parts.append(f"Fine print: {d}")

                if parts:
                    log.info(f"[{self.scraper_key}] incentive matched via {selectors['container']}")
                    return "\n\n".join(parts)
            except Exception as e:
                log.debug(f"[{self.scraper_key}] selector {selectors['container']} failed: {e}")
                continue

        return None

    async def run(self) -> ScrapeResult:
        """Two-page fetch: floorplans for units, home for incentive."""
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

                # Page 1: floorplans / suites → units
                page = await context.new_page()
                log.info(f"[{self.scraper_key}] fetching units page: {self.url}")
                await page.goto(self.url, timeout=self.page_load_timeout_ms,
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(self.post_load_wait_ms)
                units = await self.extract_units(page)
                log.info(f"[{self.scraper_key}] extracted {len(units)} units")

                # Page 2: home → incentive
                incentive_raw: str | None = None
                incentive_source_url: str | None = None
                if self.home_url:
                    try:
                        home_page = await context.new_page()
                        log.info(f"[{self.scraper_key}] fetching home: {self.home_url}")
                        await home_page.goto(self.home_url,
                                             timeout=self.page_load_timeout_ms,
                                             wait_until="domcontentloaded")
                        await home_page.wait_for_timeout(self.post_load_wait_ms)
                        incentive_raw = await self.extract_incentive(home_page)
                        if incentive_raw:
                            incentive_source_url = self.home_url
                            log.info(f"[{self.scraper_key}] got incentive ({len(incentive_raw)} chars)")
                        else:
                            log.info(f"[{self.scraper_key}] no incentive found on home page")
                        await home_page.close()
                    except Exception as e:
                        log.warning(f"[{self.scraper_key}] incentive fetch failed: {e}")

                return ScrapeResult(
                    building_name=self.name,
                    scraper_key=self.scraper_key,
                    status="success",
                    units=units,
                    source_url=self.url,
                    incentive_raw=incentive_raw,
                    incentive_source_url=incentive_source_url,
                )
            except Exception as e:
                log.exception(f"[{self.scraper_key}] scrape failed")
                return ScrapeResult(
                    building_name=self.name,
                    scraper_key=self.scraper_key,
                    status="failed",
                    error=f"{type(e).__name__}: {e}",
                    source_url=self.url,
                )
            finally:
                if browser is not None:
                    await browser.close()
