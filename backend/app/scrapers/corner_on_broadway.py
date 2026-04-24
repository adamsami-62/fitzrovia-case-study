"""Corner on Broadway — 223 Redpath Avenue, Toronto.

Reserve Properties / Westdale Properties luxury rental. Uses a dedicated marketing
site (thecornerrentals.com) that renders unit data client-side via Vue from an
external JS file at /js/suites.js.

Scraping strategy (no Playwright required):
  1. Fetch /js/suites.js directly. The file defines `var suitData = [...]` — a
     JSON-ish array of floorplan objects. Strip JS line comments (some entries
     are commented out, e.g. 1-F, 2+D-A) then json.loads the array.
  2. Fetch /suites HTML for the incentive banner from the <div class="promo">
     block.

Listing granularity: floorplan_template. The site exposes suite CODES (J-2, 1+D-A,
3+D-A) and a starting-from price per floorplan — not individual unit numbers,
floors, or availability dates.

Unit type conventions (decided with Adam):
  - "Junior 1" → "1-bed"  (industry convention; prevents single-building category
    fragmentation in cross-building comparisons)
  - "1+Den" → "1-bed + den"
  - "1", "2", "3" → "1-bed", "2-bed", "3-bed"
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin

import httpx

from backend.app.scrapers.base import BaseScraper, normalize_unit_type
from backend.app.scrapers.schema import ScrapeResult, ScrapedUnit

log = logging.getLogger(__name__)


SITE_BASE = "https://thecornerrentals.com"
SUITES_JS_URL = f"{SITE_BASE}/js/suites.js"
SUITES_HTML_URL = f"{SITE_BASE}/suites"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

# Matches the `var suitData = [ ... ]` literal and captures the array contents.
# Non-greedy up to the final closing bracket on its own line.
SUITDATA_PATTERN = re.compile(
    r"var\s+suitData\s*=\s*(\[.*?\])\s*;?\s*$",
    re.DOTALL | re.MULTILINE,
)

# Promo banner lives in <div class="promo"> ... <h2>MULTILINE TEXT</h2>.
# Capture everything inside the <h2>, including nested <br>, <span>, etc.
PROMO_PATTERN = re.compile(
    r'<div class="promo[^"]*">.*?<h2[^>]*>(.*?)</h2>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_js_line_comments(source: str) -> str:
    """Remove // ... line comments from a JS-ish source.

    Safe here because no string value in suites.js contains a literal '//'
    (paths are single-slash like /pdf/floorplan_samples/..., and text strings
    are plain prose). We strip per-line rather than parsing strings so that
    commented-out object entries collapse cleanly.
    """
    stripped_lines = []
    for line in source.splitlines():
        # Only strip comments that start with // preceded by optional whitespace
        # OR by a comma + whitespace (common case: `}, // trailing comment`).
        # For this file, all commented-out entries start lines with whitespace+//
        # so a simple leading-whitespace check works.
        stripped = re.sub(r"\s*//.*$", "", line)
        if stripped.strip():
            stripped_lines.append(stripped)
    return "\n".join(stripped_lines)


def _clean_json_array(js_array_text: str) -> str:
    """Clean a JS-style array literal into strict JSON.

    Handles: trailing commas before ] or }.
    """
    # Remove trailing commas before closing brackets/braces.
    cleaned = re.sub(r",\s*([\]}])", r"\1", js_array_text)
    return cleaned


def _parse_rent(starting_from: str) -> float | None:
    """Parse '$2150.00/mth' or '$2,563.50/mth' -> 2150.0."""
    m = re.search(r"\$([\d,]+(?:\.\d+)?)", starting_from)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_sqft(sqft_str: str) -> int | None:
    """Parse '437' or '437 Sq.Ft.' -> 437."""
    m = re.search(r"(\d+)", sqft_str)
    return int(m.group(1)) if m else None


def _derive_unit_type(bedroom: str) -> str:
    """Normalize bedroom column values to our unit_type taxonomy.

    "Junior 1" -> "1-bed"  (industry convention, avoids category fragmentation)
    "1"        -> "1-bed"
    "1+Den"    -> "1-bed + den"
    "2"        -> "2-bed"
    "2+Den"    -> "2-bed + den"
    "3"        -> "3-bed"
    """
    b = bedroom.strip().lower()
    if b.startswith("junior"):
        return normalize_unit_type("1 bed")
    # Match digit + optional "+den"
    m = re.match(r"(\d+)\s*(\+\s*den)?", b)
    if not m:
        return "unknown"
    count = m.group(1)
    den_suffix = " + den" if m.group(2) else ""
    return normalize_unit_type(f"{count} bed{den_suffix}")


def _clean_promo_text(raw_h2: str) -> str:
    """Flatten an <h2> containing <br>, <span>, and nested tags into plain text."""
    # Replace <br> variants with spaces so line breaks become natural spaces.
    text = re.sub(r"<br\s*/?>", " ", raw_h2, flags=re.IGNORECASE)
    # Strip all remaining HTML tags.
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    return text


class CornerOnBroadwayScraper(BaseScraper):
    name = "Corner on Broadway"
    scraper_key = "corner_on_broadway"
    url = SUITES_HTML_URL

    async def run(self) -> ScrapeResult:
        result = ScrapeResult(
            building_name=self.name,
            scraper_key=self.scraper_key,
            status="failed",
            units=[],
            source_url=SUITES_JS_URL,
        )

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                # 1. Fetch suites.js and parse the suitData array.
                log.info(f"[{self.scraper_key}] fetching {SUITES_JS_URL}")
                js_resp = await client.get(SUITES_JS_URL)
                js_resp.raise_for_status()

                js_clean = _strip_js_line_comments(js_resp.text)
                array_match = SUITDATA_PATTERN.search(js_clean)
                if not array_match:
                    result.error = "suitData array not found in suites.js"
                    log.error(f"[{self.scraper_key}] {result.error}")
                    return result

                json_text = _clean_json_array(array_match.group(1))
                try:
                    suites = json.loads(json_text)
                except json.JSONDecodeError as e:
                    result.error = f"JSON parse failed: {e}"
                    log.error(f"[{self.scraper_key}] {result.error}")
                    return result

                log.info(f"[{self.scraper_key}] parsed {len(suites)} floorplans")

                units: list[ScrapedUnit] = []
                for suite in suites:
                    code = str(suite.get("suite_html") or "").strip()
                    if not code:
                        continue

                    rent = _parse_rent(str(suite.get("starting_from") or ""))
                    if rent is None or rent <= 0:
                        log.warning(f"[{self.scraper_key}] suite {code}: bad rent {suite.get('starting_from')!r}, skipping")
                        continue

                    sqft = _parse_sqft(str(suite.get("int_sqft") or ""))
                    unit_type = _derive_unit_type(str(suite.get("bedroom") or ""))

                    pdf_rel = str(suite.get("pdf_link") or "").strip()
                    listing_url = urljoin(SITE_BASE, pdf_rel) if pdf_rel else SUITES_HTML_URL

                    units.append(ScrapedUnit(
                        unit_identifier=code,
                        unit_type=unit_type,
                        rent=rent,
                        sqft=sqft,
                        incentive_raw=None,
                        floor=None,
                        available_date=None,
                        listing_url=listing_url,
                        listing_type="floorplan_template",
                    ))

                result.units = units
                result.status = "success"

                # 2. Fetch the HTML page for the promo banner.
                try:
                    log.info(f"[{self.scraper_key}] fetching {SUITES_HTML_URL}")
                    html_resp = await client.get(SUITES_HTML_URL)
                    html_resp.raise_for_status()
                    m = PROMO_PATTERN.search(html_resp.text)
                    if m:
                        banner_text = _clean_promo_text(m.group(1))
                        if banner_text:
                            result.incentive_raw = banner_text
                            result.incentive_source_url = SUITES_HTML_URL
                            log.info(f"[{self.scraper_key}] incentive: {banner_text}")
                    else:
                        log.info(f"[{self.scraper_key}] no promo banner found")
                except Exception as e:
                    log.warning(f"[{self.scraper_key}] banner fetch failed: {e}")

                return result

        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}"
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

    async def extract_units(self, page):
        raise NotImplementedError("CornerOnBroadway uses run() directly.")
