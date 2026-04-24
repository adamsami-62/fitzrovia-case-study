"""Tricon Living custom scraper (The Selby, etc.).

Tricon properties use a Vue-powered widget with 3 tabs: "Interactive Tower"
(map), "Floor Plans", and "List View". List-view DOM (.TableList-item rows)
is only rendered AFTER the user clicks the "List View" tab — not on scroll,
not on initial load. So the flow must be:

    1. Load page
    2. Dismiss cookie banner if present (can intercept clicks)
    3. Scroll widget into view (to trigger Vue mount)
    4. Wait for tab buttons to exist
    5. Click "List View" tab
    6. Wait for .TableList-item to appear
    7. Click "Load More" in a loop until button is gone
    8. Parse each row

We inherit from BaseScraper directly (not RentSyncBase) because incentive
is on the same page, not a separate home page. We override run() to mirror
RentSyncBaseScraper's structure for codebase consistency.

Rent is shown as a RANGE ($4,425-$5,315/mo); we store MIN as canonical `rent`.
"""
from __future__ import annotations

import logging
import re
from playwright.async_api import async_playwright, Browser, Page

from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


_RENT_RE = re.compile(r"\$([\d,]+)")


def _parse_min_rent(text):
    if not text:
        return None
    matches = _RENT_RE.findall(text)
    if not matches:
        return None
    try:
        return min(float(m.replace(",", "")) for m in matches)
    except ValueError:
        return None


def _parse_sqft(text):
    if not text:
        return None
    m = re.search(r"\d[\d,]*", text)
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _unit_type_from_beds(beds):
    if beds <= 0:
        return "bachelor"
    if beds == 1:
        return "1-bed"
    if beds == 2:
        return "2-bed"
    if beds == 3:
        return "3-bed"
    return "unknown"


TRICON_INCENTIVE_SELECTORS = [
    ".cover-slideshow .wp-block-cover",
    "[class*='cta-popup'] .wp-block-cover",
]

OFFER_KEYWORDS = ["free", "month", "lease", "off", "special", "offer", "promo"]


class TriconBaseScraper(BaseScraper):
    widget_ready_timeout_ms: int = 25_000
    list_render_timeout_ms: int = 15_000
    max_load_more_clicks: int = 50

    async def _dismiss_cookies(self, page: Page) -> None:
        """Tricon's site uses OneTrust, which overlays a .onetrust-pc-dark-filter
        that intercepts clicks on the widget. Cover all the common OneTrust
        accept buttons plus the legacy text-match fallbacks."""
        for selector in [
            "#onetrust-accept-btn-handler",           # OneTrust standard
            "#onetrust-reject-all-handler",           # OneTrust (reject also dismisses overlay)
            "button:has-text('Accept All Cookies')",
            "button:has-text('Accept All')",
            "button:has-text('Accept')",
        ]:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=3000)
                    await page.wait_for_timeout(500)
                    log.info(f"[{self.scraper_key}] dismissed cookie banner")
                    return
            except Exception:
                continue

    async def _scroll_widget_into_view(self, page: Page) -> None:
        """Scroll so the 'List View' tab button is in the viewport.
        This triggers Vue's lazy-mount of the widget."""
        try:
            # Scroll progressively through the page to trigger any lazy init
            vh = await page.evaluate("window.innerHeight")
            ph = await page.evaluate("document.body.scrollHeight")
            for i in range(int(ph / vh) + 1):
                await page.evaluate(f"window.scrollTo(0, {i * vh})")
                await page.wait_for_timeout(250)
            # Scroll the tab button into view specifically
            btn = page.locator("button:has-text('List View')").first
            if await btn.count() > 0:
                await btn.scroll_into_view_if_needed(timeout=5000)
            await page.wait_for_timeout(800)
        except Exception as e:
            log.warning(f"[{self.scraper_key}] scroll failed: {e}")

    async def _click_list_view_tab(self, page: Page) -> bool:
        """Click 'List View'. Wait for .TableList-item to appear."""
        try:
            btn = page.locator("button:has-text('List View')").first
            # Wait for the button to be visible first
            await btn.wait_for(state="visible", timeout=self.widget_ready_timeout_ms)
            await btn.scroll_into_view_if_needed(timeout=3000)
            await btn.click(timeout=5000)
            log.info(f"[{self.scraper_key}] clicked List View tab")
            # Now wait for the list to render
            await page.wait_for_selector(
                ".TableList-item",
                timeout=self.list_render_timeout_ms,
            )
            log.info(f"[{self.scraper_key}] list rendered")
            return True
        except Exception as e:
            log.warning(f"[{self.scraper_key}] list view click/render failed: {e}")
            return False

    async def _click_load_more_until_gone(self, page: Page) -> int:
        clicks = 0
        for _ in range(self.max_load_more_clicks):
            try:
                btn = page.locator("button:has-text('Load More')").first
                if await btn.count() == 0 or not await btn.is_visible():
                    break
                rows_before = await page.locator(".TableList-item").count()
                await btn.scroll_into_view_if_needed(timeout=3000)
                await btn.click(timeout=5000)
                clicks += 1
                changed = False
                for _ in range(15):
                    await page.wait_for_timeout(200)
                    if await page.locator(".TableList-item").count() > rows_before:
                        changed = True
                        break
                if not changed:
                    log.info(f"[{self.scraper_key}] Load More #{clicks} added no rows; stopping")
                    break
            except Exception as e:
                log.warning(f"[{self.scraper_key}] Load More error: {e}")
                break
        log.info(f"[{self.scraper_key}] clicked Load More {clicks} times")
        return clicks

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        rows = page.locator(".TableList-item")
        count = await rows.count()
        units: list[ScrapedUnit] = []
        for i in range(count):
            row = rows.nth(i)
            try:
                num_el = row.locator(".TableList-col.isNumber").first
                unit_id = ""
                if await num_el.count() > 0:
                    raw = (await num_el.inner_text()).strip()
                    unit_id = raw.lstrip("#").strip()
                if not unit_id:
                    continue

                rent_el = row.locator(".TableList-col.isRent").first
                rent_text = (await rent_el.inner_text()).strip() if await rent_el.count() > 0 else ""
                rent = _parse_min_rent(rent_text)
                if rent is None:
                    continue

                beds_el = row.locator(".TableList-col.isBeds").first
                beds_text = (await beds_el.inner_text()).strip() if await beds_el.count() > 0 else ""
                try:
                    beds = int(beds_text) if beds_text.isdigit() else 0
                except ValueError:
                    beds = 0

                sqft_el = row.locator(".TableList-col.isSqft").first
                sqft_text = (await sqft_el.inner_text()).strip() if await sqft_el.count() > 0 else ""
                sqft = _parse_sqft(sqft_text)

                floor_el = row.locator(".UnitsList-floorNumber").first
                floor = None
                if await floor_el.count() > 0:
                    ftxt = (await floor_el.inner_text()).strip()
                    try:
                        floor = int(ftxt)
                    except ValueError:
                        pass

                avail_el = row.locator(".TableList-col.isAvailability span").first
                avail_text = (await avail_el.inner_text()).strip() if await avail_el.count() > 0 else ""
                available_date = None
                if avail_text and avail_text.lower() not in ("available", "coming soon"):
                    available_date = avail_text

                units.append(ScrapedUnit(
                    unit_identifier=unit_id,
                    unit_type=_unit_type_from_beds(beds),
                    rent=rent,
                    sqft=sqft,
                    incentive_raw=None,
                    floor=floor,
                    available_date=available_date,
                    listing_url=self.url,
                    listing_type="specific_unit",
                ))
            except Exception as e:
                log.warning(f"[{self.scraper_key}] row {i} parse failed: {e}")
        return units

    async def extract_incentive(self, page: Page) -> str | None:
        for selector in TRICON_INCENTIVE_SELECTORS:
            try:
                els = page.locator(selector)
                n = await els.count()
                for i in range(n):
                    el = els.nth(i)
                    try:
                        text = (await el.inner_text()).strip()
                    except Exception:
                        continue
                    if not text:
                        continue
                    low = text.lower()
                    if any(k in low for k in OFFER_KEYWORDS):
                        log.info(f"[{self.scraper_key}] incentive matched via {selector}")
                        return text[:2000]
            except Exception:
                continue
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

                log.info(f"[{self.scraper_key}] fetching: {self.url}")
                await page.goto(self.url, timeout=self.page_load_timeout_ms,
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(self.post_load_wait_ms)

                await self._dismiss_cookies(page)
                await self._scroll_widget_into_view(page)
                if not await self._click_list_view_tab(page):
                    raise RuntimeError(
                        "Failed to open List View tab — likely a cookie banner "
                        "intercepted the click. Check _dismiss_cookies selectors."
                    )
                await self._click_load_more_until_gone(page)

                units = await self.extract_units(page)
                log.info(f"[{self.scraper_key}] extracted {len(units)} units")

                incentive_raw = await self.extract_incentive(page)
                incentive_source_url = self.url if incentive_raw else None

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
