"""Story of Midtown — 73 & 75 Broadway Avenue, Toronto.

The website lists two distinct addresses (new tower and revitalized legacy
building) under a single domain, with tab switching between them. Each is
its own building in our DB because they have different price points,
different build vintages, and different CMS floorplan keys.
"""
from backend.app.scrapers.rentsync_navigator import RentSyncNavigatorScraper


class StoryOfMidtown73Scraper(RentSyncNavigatorScraper):
    name = "Story of Midtown (73 Broadway - New)"
    scraper_key = "story_of_midtown_73"
    url = "https://www.mystorymidtown.com/suites"
    home_url = "https://www.mystorymidtown.com/"
    tab_keyword = "73 Broadway"


class StoryOfMidtown75Scraper(RentSyncNavigatorScraper):
    name = "Story of Midtown (75 Broadway - Revitalized)"
    scraper_key = "story_of_midtown_75"
    url = "https://www.mystorymidtown.com/suites"
    home_url = "https://www.mystorymidtown.com/"
    tab_keyword = "75 Broadway"
