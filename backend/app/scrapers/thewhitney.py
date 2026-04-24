"""The Whitney — 71 Redpath Avenue, Toronto. Fitzrovia property.

WordPress + Elementor custom build. No CMS widget; floorplan rows are
server-rendered inside the /apartments page as nested Elementor containers.
Each floorplan has a [data-link] anchor pointing to its detail page slug;
unavailable floorplans get the .d-none CSS class applied to their row.

Listing granularity: floorplan_template (no individual unit numbers shown).
unit_identifier is the floorplan display name (AZURE, CINNAMON, etc.).

Incentive scan: checks home page for common promo containers. Whitney does
not currently publish an incentive; the scan defensively covers future
additions without failing if nothing is found.
"""
from __future__ import annotations

import logging
from playwright.async_api import async_playwright, Browser, Page

from backend.app.scrapers.base import BaseScraper, normalize_unit_type, parse_rent, parse_sqft
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


BASE_DOMAIN = "https://www.thewhitneyonredpath.com"

WHITNEY_INCENTIVE_SELECTORS = [
    ".home-popup",
    "#home-popup",
    ".promo-banner",
    "[class*=\"promo\"]",
    "[class*=\"incentive\"]",
    "[class*=\"offer\"]",
    "[class*=\"special\"]",
]

OFFER_KEYWORDS = ["free", "month", "off", "promo", "special", "incentive", "bonus"]


class WhitneyScraper(BaseScraper):
    name = "The Whitney"
    scraper_key = "the_whitney"
    url = "https://www.thewhitneyonredpath.com/apartments/"
    home_url = "https://www.thewhitneyonredpath.com/"

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        anchors = page.locator("[data-link]")
        total = await anchors.count()

        seen_slugs: set[str] = set()
        units: list[ScrapedUnit] = []

        for i in range(total):
            a = anchors.nth(i)
            slug = await a.get_attribute("data-link")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            row = a.locator("xpath=..")
            if not await row.is_visible():
                continue

            paragraphs = await row.locator("p").all_text_contents()
            if len(paragraphs) < 5:
                log.warning(f"[{self.scraper_key}] slug {slug}: only {len(paragraphs)} <p> tags, skipping")
                continue

            name = paragraphs[0].strip()
            beds_baths = paragraphs[2]
            sqft_text = paragraphs[3]
            rent_text = paragraphs[4]

            rent = parse_rent(rent_text)
            if rent is None:
                log.warning(f"[{self.scraper_key}] slug {slug}: could not parse rent \"{rent_text}\"")
                continue

            listing_url = slug if slug.startswith("http") else f"{BASE_DOMAIN}{slug}"

            units.append(ScrapedUnit(
                unit_identifier=name,
                unit_type=normalize_unit_type(beds_baths),
                rent=rent,
                sqft=parse_sqft(sqft_text),
                incentive_raw=None,
                floor=None,
                available_date=None,
                listing_url=listing_url,
                listing_type="floorplan_template",
            ))

        return units

    async def extract_incentive(self, page: Page) -> str | None:
        for selector in WHITNEY_INCENTIVE_SELECTORS:
            try:
                els = page.locator(selector)
                n = await els.count()
                for i in range(n):
                    el = els.nth(i)
                    try:
                        text = (await el.inner_text()).strip()
                    except Exception:
                        continue
                    if not text or len(text) < 10:
                        continue
                    low = text.lower()
                    if any(k in low for k in OFFER_KEYWORDS):
                        log.info(f"[{self.scraper_key}] incentive matched via {selector}")
                        return text[:2000]
            except Exception:
                continue
        log.info(f"[{self.scraper_key}] no incentive found")
        return None

    async def run(self) -> ScrapeResult:
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
                log.info(f"[{self.scraper_key}] fetching units: {self.url}")
                await page.goto(self.url, timeout=self.page_load_timeout_ms,
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(self.post_load_wait_ms)
                units = await self.extract_units(page)
                log.info(f"[{self.scraper_key}] extracted {len(units)} floorplans")

                incentive_raw = None
                incentive_source_url = None
                try:
                    home = await context.new_page()
                    log.info(f"[{self.scraper_key}] fetching home: {self.home_url}")
                    await home.goto(self.home_url,
                                    timeout=self.page_load_timeout_ms,
                                    wait_until="domcontentloaded")
                    await home.wait_for_timeout(self.post_load_wait_ms)
                    incentive_raw = await self.extract_incentive(home)
                    if incentive_raw:
                        incentive_source_url = self.home_url
                    await home.close()
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
