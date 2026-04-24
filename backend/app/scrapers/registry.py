"""Central list of every scraper class. Used by runner + scrape endpoint.

Keeping this in one place means test_all_scrapers.py, the scrape endpoint,
and any future cron job all agree on what "all scrapers" means.
"""
from backend.app.scrapers.akoya import AkoyaScraper
from backend.app.scrapers.corner_on_broadway import CornerOnBroadwayScraper
from backend.app.scrapers.e18hteen import E18hteenScraper
from backend.app.scrapers.ecentral import ECentralScraper
from backend.app.scrapers.parker import ParkerScraper
from backend.app.scrapers.selby import SelbyScraper
from backend.app.scrapers.story_of_midtown import (
    StoryOfMidtown73Scraper,
    StoryOfMidtown75Scraper,
)
from backend.app.scrapers.thehampton import TheHamptonScraper
from backend.app.scrapers.themontgomery import TheMontgomeryScraper
from backend.app.scrapers.thewhitney import WhitneyScraper


ALL_SCRAPER_CLASSES = [
    ParkerScraper,
    StoryOfMidtown73Scraper,
    StoryOfMidtown75Scraper,
    SelbyScraper,
    ECentralScraper,
    TheMontgomeryScraper,
    WhitneyScraper,
    TheHamptonScraper,
    E18hteenScraper,
    CornerOnBroadwayScraper,
    AkoyaScraper,
]


def instantiate_all():
    return [cls() for cls in ALL_SCRAPER_CLASSES]
