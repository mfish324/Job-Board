"""
Base scraper class for ATS job boards.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all ATS scrapers."""

    ATS_NAME: str = 'other'

    def __init__(self, company_identifier: str, company_name: Optional[str] = None):
        """
        Initialize scraper.

        Args:
            company_identifier: The company's slug/ID on the ATS platform
            company_name: Human-readable company name (auto-detected if not provided)
        """
        self.company_identifier = company_identifier
        self.company_name = company_name

    @abstractmethod
    def get_job_list_url(self) -> str:
        """Return the URL to fetch the job listings."""
        pass

    @abstractmethod
    def fetch_listings(self) -> List[Dict]:
        """
        Fetch all job listings from the ATS.

        Returns:
            List of job dictionaries in standardized format
        """
        pass

    @abstractmethod
    def fetch_job_details(self, job_id: str) -> Dict:
        """
        Fetch full details for a single job.

        Args:
            job_id: The job's ID on the ATS platform

        Returns:
            Job dictionary with full details
        """
        pass

    def standardize_job(self, raw_job: Dict) -> Dict:
        """
        Convert ATS-specific job format to standard format.

        Subclasses should override this to handle their specific format.
        """
        return {
            'source_ats': self.ATS_NAME,
            'source_url': raw_job.get('absolute_url', ''),
            'external_requisition_id': str(raw_job.get('id', '')),
            'company_name': self.company_name or self.company_identifier,
            'title': raw_job.get('title', 'Untitled'),
            'description': raw_job.get('content', ''),
            'location': self._extract_location(raw_job),
            'job_type': self._map_job_type(raw_job.get('employment_type')),
            'remote_status': self._extract_remote_status(raw_job),
            'salary_min': raw_job.get('salary_min'),
            'salary_max': raw_job.get('salary_max'),
            'salary_currency': raw_job.get('salary_currency', 'USD'),
            'department': raw_job.get('department'),
            'raw_data': raw_job,
        }

    def _extract_location(self, job: Dict) -> Optional[str]:
        """Extract location string from job data."""
        if 'location' in job:
            loc = job['location']
            if isinstance(loc, dict):
                return loc.get('name', str(loc))
            return str(loc)
        return None

    def _extract_remote_status(self, job: Dict) -> Optional[str]:
        """Extract remote status from job data."""
        title = job.get('title', '').lower()
        location = str(job.get('location', '')).lower()

        if 'remote' in title or 'remote' in location:
            if 'hybrid' in title or 'hybrid' in location:
                return 'hybrid'
            return 'remote'
        return 'on_site'

    def _map_job_type(self, employment_type: Optional[str]) -> Optional[str]:
        """Map ATS employment type to standard job type."""
        if not employment_type:
            return None

        mapping = {
            'full-time': 'full_time',
            'full time': 'full_time',
            'fulltime': 'full_time',
            'part-time': 'part_time',
            'part time': 'part_time',
            'parttime': 'part_time',
            'contract': 'contract',
            'contractor': 'contract',
            'temporary': 'temporary',
            'temp': 'temporary',
            'intern': 'internship',
            'internship': 'internship',
            'freelance': 'freelance',
        }

        return mapping.get(employment_type.lower(), None)

    def scrape_all(self) -> List[Dict]:
        """
        Full scrape: fetch listing list, then details for each.

        Returns:
            List of standardized job dictionaries
        """
        logger.info(f"Starting scrape for {self.company_name or self.company_identifier}")

        try:
            listings = self.fetch_listings()
            logger.info(f"Found {len(listings)} listings")

            standardized = []
            for job in listings:
                try:
                    std_job = self.standardize_job(job)
                    standardized.append(std_job)
                except Exception as e:
                    logger.error(f"Error standardizing job: {e}")

            return standardized

        except Exception as e:
            logger.error(f"Error scraping {self.company_identifier}: {e}")
            return []
