"""
Job scraper modules for various ATS platforms.

Each scraper provides methods to fetch job listings from public job board pages
and convert them to the format expected by ScrapedJobListing.
"""

from .greenhouse import GreenhouseScraper
from .lever import LeverScraper
from .base import BaseScraper

__all__ = ['BaseScraper', 'GreenhouseScraper', 'LeverScraper']
