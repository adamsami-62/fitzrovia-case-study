"""E18HTEEN — 18 Erskine Avenue, Toronto. KG Group luxury rental.

Uses the Rentsync website-gateway JSON API via MyRentalBaseScraper.
propertyId 33874 is the internal Rentsync identifier for this building.
"""
from __future__ import annotations

from backend.app.scrapers.myrental_base import MyRentalBaseScraper


class E18hteenScraper(MyRentalBaseScraper):
    name = "E18HTEEN"
    scraper_key = "e18hteen"
    property_id = 33874
    theme_slug = "kg_rebuild"
    permalink = "18-erskine-ave"
