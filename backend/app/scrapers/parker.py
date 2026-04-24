"""Parker — 200 Redpath Avenue, Toronto. RentSync embedded-JSON style."""
from backend.app.scrapers.rentsync_embedded import RentSyncEmbeddedScraper


class ParkerScraper(RentSyncEmbeddedScraper):
    name = "Parker"
    scraper_key = "parker"
    url = "https://www.parkerlife.ca/floorplans"
    home_url = "https://www.parkerlife.ca/"
