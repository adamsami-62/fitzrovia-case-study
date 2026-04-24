"""eCentral — 15 Roehampton Avenue, Toronto. RioCan Living property.

Custom jQuery/Bootstrap site with Yardi RentCafe backend (securecafe.com
for applications, cdngeneralcf.rentcafe.com for floorplan images).

The /rental-suites page server-renders one card per floorplan:

    <a class="floorplan floorplan-{id}" data-id="{id}" href="/rental-suites/{id}">
      <h3>The Revolve</h3>
      <div class="bed">0<span>BEDROOM</span></div>
      <div class="bath">1<span>BATH</span></div>
      <div class="size">583 <span>SQ.FT.</span></div>
      <div class="price"><strong>Starting At </strong>$2045</div>
      <div class="available">13/05/2026</div>  -- or "Available Now"
    </a>

Note: the live availability string is populated by JS after initial load,
via a securecafe AJAX call keyed on the floorplan id. We wait for that to
finish before reading the .available text.

This is floorplan-TEMPLATE granularity (no individual unit numbers shown),
so rows are emitted with listing_type='floorplan_template'. The unit_identifier
is the floorplan's display name (e.g. 'The Centric') which is the most
human-readable stable key for dashboards. The FloorplanId (3526636 etc.)
is captured inside the listing_url for traceability.

Incentive is a modal on the HOME page (#site-popup), not the suites page.
Two-page flow like RentSync.

Availability dates are shown as D/M/Y (European) on the page — we normalize
to ISO YYYY-MM-DD for DB storage.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page

from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


def _unit_type_from_beds(n: int) -> str:
    if n <= 0:
        return "bachelor"
    if n == 1:
        return "1-bed"
    if n == 2:
        return "2-bed"
    if n == 3:
        return "3-bed"
    return "unknown"


def _parse_date(text: str) -> str | None:
    """'13/05/2026' -> '2026-05-13'. 'Available Now' -> None.
    Unparseable -> None (logged upstream)."""
    if not text:
        return None
    t = text.strip()
    if not t or t.lower() in ("available now", "available", "n/a"):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class ECentralScraper(BaseScraper):
    name = "eCentral"
    scraper_key = "ecentral"
    url = "https://www.ecentralliving.com/rental-suites"
    home_url = "https://www.ecentralliving.com/"

    # Wait for securecafe AJAX to populate .available text on each card.
    availability_render_wait_ms: int = 5_000

    async def _extract_card(self, card) -> ScrapedUnit | None:
        """Parse one <a.floorplan> card into a ScrapedUnit, or None if invalid."""
        try:
            data_id = await card.get_attribute("data-id")
            href = await card.get_attribute("href")

            # Name from <h3>
            name_el = card.locator("h3").first
            name = (await name_el.inner_text()).strip() if await name_el.count() > 0 else ""
            if not name:
                return None

            # Bed count: .bed div's text starts with the number, then "BEDROOM" span
            bed_el = card.locator(".bed").first
            beds = 0
            if await bed_el.count() > 0:
                bed_text = (await bed_el.inner_text()).strip()
                m = re.match(r"^\s*(\d+)", bed_text)
                if m:
                    beds = int(m.group(1))

            # Sqft: .size div text starts with the number (may contain comma)
            size_el = card.locator(".size").first
            sqft = None
            if await size_el.count() > 0:
                size_text = (await size_el.inner_text()).strip()
                m = re.search(r"([\d,]+)", size_text)
                if m:
                    try:
                        sqft = int(m.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # Rent: .price contains 'Starting At $2045'
            price_el = card.locator(".price").first
            rent = None
            if await price_el.count() > 0:
                price_text = (await price_el.inner_text()).strip()
                m = re.search(r"\$?([\d,]+)", price_text.replace("Starting At", ""))
                if m:
                    try:
                        rent = float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass
            if rent is None:
                return None

            # Availability: .available div
            avail_el = card.locator(".available").first
            avail_text = ""
            if await avail_el.count() > 0:
                avail_text = (await avail_el.inner_text()).strip()
            available_date = _parse_date(avail_text)

            # Full listing URL (absolute); include FloorplanId for traceability
            listing_url = self.url
            if href:
                if href.startswith("/"):
                    listing_url = f"https://www.ecentralliving.com{href}"
                else:
                    listing_url = href

            return ScrapedUnit(
                unit_identifier=name,                       # e.g. 'The Centric'
                unit_type=_unit_type_from_beds(beds),
                rent=rent,
                sqft=sqft,
                incentive_raw=None,
                floor=None,                                 # not exposed at template level
                available_date=available_date,
                listing_url=listing_url,
                listing_type="floorplan_template",
            )
        except Exception as e:
            log.warning(f"[{self.scraper_key}] card parse failed: {e}")
            return None

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        # Wait for JS to populate .available text on each card
        await page.wait_for_timeout(self.availability_render_wait_ms)

        cards = page.locator("a.floorplan[data-id]")
        n = await cards.count()
        log.info(f"[{self.scraper_key}] found {n} floorplan cards")

        units: list[ScrapedUnit] = []
        for i in range(n):
            u = await self._extract_card(cards.nth(i))
            if u is not None:
                units.append(u)
        return units

    async def extract_incentive(self, home_page: Page) -> str | None:
        """Read #site-popup .text-wrapper from the home page."""
        try:
            popup = home_page.locator("#site-popup").first
            if await popup.count() == 0:
                log.info(f"[{self.scraper_key}] no #site-popup on home")
                return None
            wrapper = popup.locator(".text-wrapper").first
            target = wrapper if await wrapper.count() > 0 else popup
            text = (await target.inner_text()).strip()
            if text:
                log.info(f"[{self.scraper_key}] incentive matched via #site-popup")
                return text[:2000]
        except Exception as e:
            log.warning(f"[{self.scraper_key}] incentive read failed: {e}")
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

                # Page 1: /rental-suites for unit cards
                page = await context.new_page()
                log.info(f"[{self.scraper_key}] fetching units: {self.url}")
                await page.goto(self.url, timeout=self.page_load_timeout_ms,
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(self.post_load_wait_ms)
                units = await self.extract_units(page)
                log.info(f"[{self.scraper_key}] extracted {len(units)} floorplans")

                # Page 2: home page for the #site-popup incentive
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
                        log.info(f"[{self.scraper_key}] got incentive ({len(incentive_raw)} chars)")
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
