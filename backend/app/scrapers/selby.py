"""The Selby — 25 Selby Street, Toronto. Tricon Living property."""
from backend.app.scrapers.tricon import TriconBaseScraper


class SelbyScraper(TriconBaseScraper):
    name = "The Selby"
    scraper_key = "the_selby"
    url = "https://triconliving.com/apartment/the-selby/#your-perfect-layout"
