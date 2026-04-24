"""RentSync floorplan-navigator widget scraper (Story of Midtown style).

Current state: scrapes the currently-visible floor on each tab.

Known TODO: the widget uses a cyclic floor navigator (< / > arrows) which we
do not yet traverse. That would require clicking into each floor per tab and
accumulating units. Deferred because the single-floor default still produces
real market-comparable data and the pagination is site-specific enough that
iterating on it shouldn't block end-to-end product completion.
"""
from __future__ import annotations

import logging
import re
from playwright.async_api import Page

from backend.app.scrapers.rentsync_base import (
    RentSyncBaseScraper, unit_type_from_bed_count,
)
from backend.app.scrapers.schema import ScrapedUnit

log = logging.getLogger(__name__)


_RENT_RE = re.compile(r"[\d,.]+")


def _parse_rent(text):
    if not text: return None
    m = _RENT_RE.search(text)
    if not m: return None
    try: return float(m.group(0).replace(",", ""))
    except ValueError: return None


def _parse_sqft(text):
    if not text: return None
    m = re.search(r"\d[\d,]*", text)
    if not m: return None
    try: return int(m.group(0).replace(",", ""))
    except ValueError: return None


def _parse_beds(text):
    if not text: return 0
    t = text.strip().lower()
    if "studio" in t or "bachelor" in t: return 0
    m = re.search(r"(\d+)", t)
    return int(m.group(1)) if m else 0


def _parse_floor_from_unit_number(unit_num):
    if not unit_num: return None
    digits = re.sub(r"\D", "", unit_num)
    if len(digits) < 3: return None
    try: return int(digits[:-2])
    except ValueError: return None


class RentSyncNavigatorScraper(RentSyncBaseScraper):
    """For sites using the <floorplan-navigator> widget.

    Subclasses set:
        tab_keyword — substring of tab button text (e.g. "73 Broadway")
    """
    tab_keyword: str | None = None
    widget_ready_timeout_ms: int = 25000

    async def _trigger_scrollspy(self, page: Page) -> None:
        try:
            vh = await page.evaluate("window.innerHeight")
            ph = await page.evaluate("document.body.scrollHeight")
            for i in range(int(ph / vh) + 1):
                await page.evaluate(f"window.scrollTo(0, {i * vh})")
                await page.wait_for_timeout(220)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)
        except Exception as e:
            log.warning(f"[{self.scraper_key}] scrollspy trigger failed: {e}")

    async def _click_tab(self, page: Page) -> bool:
        if not self.tab_keyword:
            return True
        keyword = self.tab_keyword.strip().lower()
        try:
            buttons = page.locator("button.button-sage__button")
            count = await buttons.count()
            for i in range(count):
                btn = buttons.nth(i)
                text = (await btn.inner_text()).strip().lower()
                if keyword in text:
                    await btn.scroll_into_view_if_needed(timeout=5000)
                    await page.wait_for_timeout(400)
                    await btn.click(force=True, timeout=10000)
                    log.info(f"[{self.scraper_key}] clicked tab: '{text}'")
                    await page.wait_for_timeout(4000)
                    return True
            log.warning(f"[{self.scraper_key}] no tab matched '{keyword}'")
            return False
        except Exception as e:
            log.warning(f"[{self.scraper_key}] tab click error: {e}")
            return False

    async def _get_visible_nav_root(self, page: Page):
        roots = page.locator(".floorplan-navigator--listing")
        count = await roots.count()
        for i in range(count):
            r = roots.nth(i)
            try:
                if await r.is_visible():
                    return r
            except Exception:
                continue
        return None

    async def _extract_cards(self, scope) -> list[ScrapedUnit]:
        cards = scope.locator(".unit-card")
        count = await cards.count()
        seen_ids: set[str] = set()
        units = []
        for i in range(count):
            card = cards.nth(i)
            try:
                title_el = card.locator(".unit-card__title--number").first
                unit_id = ""
                if await title_el.count() > 0:
                    unit_id = (await title_el.inner_text()).strip().replace("Unit", "").strip()
                if not unit_id or unit_id in seen_ids:
                    continue
                seen_ids.add(unit_id)

                bed_el = card.locator(".unit-card__bed").first
                sqft_el = card.locator(".unit-card__sqFt").first
                rate_el = card.locator(".unit-card__rate").first

                bed_text = (await bed_el.inner_text()).strip() if await bed_el.count() > 0 else ""
                sqft_text = (await sqft_el.inner_text()).strip() if await sqft_el.count() > 0 else ""
                rate_text = (await rate_el.inner_text()).strip() if await rate_el.count() > 0 else ""

                rent = _parse_rent(rate_text)
                if rent is None:
                    continue

                avail_el = card.locator(".unit-card__available").first
                avail_text = ""
                if await avail_el.count() > 0:
                    avail_text = (await avail_el.inner_text()).strip()
                available_date = None
                if avail_text and "now" not in avail_text.lower():
                    available_date = avail_text

                units.append(ScrapedUnit(
                    unit_identifier=unit_id,
                    unit_type=unit_type_from_bed_count(_parse_beds(bed_text)),
                    rent=rent,
                    sqft=_parse_sqft(sqft_text),
                    incentive_raw=None,
                    floor=_parse_floor_from_unit_number(unit_id),
                    available_date=available_date,
                    listing_url=self.url,
                    listing_type="specific_unit",
                ))
            except Exception as e:
                log.warning(f"[{self.scraper_key}] card {i} failed: {e}")
        return units

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        await self._trigger_scrollspy(page)
        try:
            await page.wait_for_selector(".unit-card", timeout=self.widget_ready_timeout_ms)
            log.info(f"[{self.scraper_key}] widget ready")
        except Exception as e:
            raise RuntimeError(f"[{self.scraper_key}] widget never rendered .unit-card") from e

        await self._click_tab(page)

        nav_root = await self._get_visible_nav_root(page)
        scope = nav_root if nav_root is not None else page
        units = await self._extract_cards(scope)
        log.info(
            f"[{self.scraper_key}] extracted {len(units)} units "
            f"(current floor only — pagination TODO)"
        )
        return units
