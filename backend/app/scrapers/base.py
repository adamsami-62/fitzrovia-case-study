"""Base class every building-specific scraper inherits from."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from playwright.async_api import async_playwright, Browser, Page

from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Contract for building scrapers.

    Subclasses set class attributes (name, key, url) and implement
    `extract_units()` which receives a ready Playwright page and returns
    a list of ScrapedUnit. Everything else — browser lifecycle, error
    wrapping, result packaging — is handled here."""

    # subclasses MUST override these
    name: str = ""
    scraper_key: str = ""
    url: str = ""

    # tweakable per-site
    page_load_timeout_ms: int = 30_000
    post_load_wait_ms: int = 2_000

    @abstractmethod
    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        """Given a loaded page, pull out every available unit."""
        ...

    async def prepare_page(self, page: Page) -> None:
        """Optional hook: click 'load more', dismiss cookie banners, etc.
        Default is a no-op."""
        return None

    async def run(self) -> ScrapeResult:
        """Orchestrates the whole scrape for this building."""
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

                log.info(f"[{self.scraper_key}] navigating to {self.url}")
                await page.goto(self.url, timeout=self.page_load_timeout_ms,
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(self.post_load_wait_ms)

                await self.prepare_page(page)

                units = await self.extract_units(page)
                log.info(f"[{self.scraper_key}] extracted {len(units)} units")

                return ScrapeResult(
                    building_name=self.name,
                    scraper_key=self.scraper_key,
                    status="success",
                    units=units,
                    source_url=self.url,
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


def normalize_unit_type(raw: str) -> str:
    """Map messy site-specific labels to our 4 canonical types."""
    r = raw.strip().lower()
    if "bachelor" in r or "studio" in r:
        return "bachelor"
    if "3" in r and "bed" in r:
        return "3-bed"
    if "2" in r and "bed" in r:
        return "2-bed"
    if "1" in r and "bed" in r or "one" in r:
        return "1-bed"
    return "unknown"


def parse_rent(raw: str) -> float | None:
    """Extract a rent number from strings like '$2,495/mo' or 'From $2,150'."""
    import re
    if not raw:
        return None
    m = re.search(r"[\d,]+", raw.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_sqft(raw: str) -> int | None:
    """Extract square footage from '650 sq ft' or '650–720 sqft'."""
    import re
    if not raw:
        return None
    m = re.search(r"\d{3,4}", raw)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None
