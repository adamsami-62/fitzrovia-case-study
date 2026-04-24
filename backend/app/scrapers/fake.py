"""A fake scraper for pipeline testing. Returns synthetic units."""
from playwright.async_api import Page

from backend.app.scrapers.base import BaseScraper
from backend.app.scrapers.schema import ScrapedUnit


class FakeScraper(BaseScraper):
    name = "Fake Building"
    scraper_key = "fake"
    url = "about:blank"

    async def extract_units(self, page: Page) -> list[ScrapedUnit]:
        return [
            ScrapedUnit(
                unit_identifier="101",
                unit_type="1-bed",
                rent=2450.0,
                sqft=620,
                incentive_raw="1 month free on 13-month lease",
                floor=1,
                available_date="2026-05-01",
                listing_url="https://example.com/unit/101",
            ),
            ScrapedUnit(
                unit_identifier="202",
                unit_type="2-bed",
                rent=3395.0,
                sqft=890,
                incentive_raw=None,
                floor=2,
            ),
            ScrapedUnit(
                unit_identifier="305",
                unit_type="bachelor",
                rent=1895.0,
                sqft=420,
                incentive_raw="Waived amenity fee",
            ),
        ]
