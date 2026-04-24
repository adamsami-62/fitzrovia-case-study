"""Akoya Living — 55 Broadway Avenue, Toronto. Times Group luxury rental.

Uses the Rentsync website-gateway JSON API via MyRentalBaseScraper with three
behavioral overrides vs KG Group properties:

  1. show_unavailable_units=False (matches Akoya's frontend; honest about
     what's currently shown to the public).
  2. listing_granularity="floorplan_template" (the gateway returns per-floorplan
     summaries with number="", typeName="Lotus I" etc. — not per-unit rows).
  3. _fetch_incentive overridden to parse the multi-promo modal on akoyaliving.ca
     home page. Akoya runs three concurrent promotions (Othership tour perk;
     2 months + $500 on 2-year leases; 1 month + $250 on 1-year leases). We
     concatenate all three so the Claude parser can structure them downstream.

propertyId 303333 is the internal Rentsync identifier.
"""
from __future__ import annotations

import logging
import re

import httpx

from backend.app.scrapers.myrental_base import MyRentalBaseScraper, USER_AGENT

log = logging.getLogger(__name__)


AKOYA_HOME_URL = "https://www.akoyaliving.ca/"

# Each promo on the home page is an <article class="...floating-promo-card...">
# containing <h3 class="...floating-promo-card__heading...">TITLE</h3>
# followed by a content wrapper. We extract the full article block, then pull
# heading + body text separately for readable concatenation.
PROMO_ARTICLE_PATTERN = re.compile(
    r'<article\s+class="[^"]*floating-promo-card[^"]*"[^>]*>(.*?)</article>',
    re.DOTALL | re.IGNORECASE,
)
HEADING_PATTERN = re.compile(
    r'<h3[^>]*floating-promo-card__heading[^>]*>(.*?)</h3>',
    re.DOTALL | re.IGNORECASE,
)
BODY_CONTENT_PATTERN = re.compile(
    r'<div[^>]*floating-promo-card__content[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_tags(html: str) -> str:
    """Flatten <br>, <li>, <p>, <strong>, etc. into plain text with spaces."""
    # Preserve structure: replace block-level closings with newlines, inline with spaces.
    html = re.sub(r'</(li|p|div|h3|ul)>', r' \n', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', r' ', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    # Decode the most common entities we see in CMS content.
    html = html.replace('&nbsp;', ' ').replace('&ndash;', '-').replace('&amp;', '&')
    # Collapse whitespace but preserve inter-promo breaks.
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n\s*\n', '\n', html)
    return html.strip()


class AkoyaScraper(MyRentalBaseScraper):
    name = "Akoya Living"
    scraper_key = "akoya_living"
    property_id = 303333
    theme_slug = "t2r_akoya"
    show_unavailable_units = False
    listing_granularity = "floorplan_template"
    # permalink not needed — incentive fetch overridden to use home page directly.
    site_base = "https://www.akoyaliving.ca"

    async def _fetch_incentive(self) -> tuple[str, str] | None:
        """Override: Akoya runs a multi-promo slider on the home page.

        Concatenates all promo cards (heading + body) with \n\n separators so
        the downstream Claude parser can see the full set of concessions.
        """
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(AKOYA_HOME_URL)
            resp.raise_for_status()

        articles = PROMO_ARTICLE_PATTERN.findall(resp.text)
        if not articles:
            log.info(f"[{self.scraper_key}] no promo articles found on home page")
            return None

        promos: list[str] = []
        for article_html in articles:
            heading_match = HEADING_PATTERN.search(article_html)
            body_match = BODY_CONTENT_PATTERN.search(article_html)
            heading = _strip_tags(heading_match.group(1)) if heading_match else ""
            body = _strip_tags(body_match.group(1)) if body_match else ""
            if heading or body:
                promos.append(f"{heading}: {body}" if heading and body else (heading or body))

        if not promos:
            return None

        combined = "\n\n".join(promos)
        log.info(f"[{self.scraper_key}] found {len(promos)} promos")
        return (combined, AKOYA_HOME_URL)
