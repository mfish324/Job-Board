"""
Greenhouse ATS scraper.

Greenhouse provides a public JSON API for job boards:
https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs

Example:
    scraper = GreenhouseScraper('stripe')  # For boards.greenhouse.io/stripe
    jobs = scraper.scrape_all()
"""

import requests
import logging
from typing import List, Dict, Optional
from .base import BaseScraper

logger = logging.getLogger(__name__)


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse job boards."""

    ATS_NAME = 'greenhouse'
    BASE_URL = 'https://boards-api.greenhouse.io/v1/boards'

    def __init__(self, board_token: str, company_name: Optional[str] = None):
        """
        Initialize Greenhouse scraper.

        Args:
            board_token: The company's Greenhouse board token (e.g., 'stripe', 'airbnb')
            company_name: Human-readable company name
        """
        super().__init__(board_token, company_name)
        self.board_token = board_token

    def get_job_list_url(self) -> str:
        return f"{self.BASE_URL}/{self.board_token}/jobs"

    def get_job_detail_url(self, job_id: str) -> str:
        return f"{self.BASE_URL}/{self.board_token}/jobs/{job_id}"

    def fetch_listings(self) -> List[Dict]:
        """Fetch all job listings from Greenhouse API."""
        url = self.get_job_list_url()
        params = {'content': 'true'}  # Include job descriptions

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Greenhouse returns {"jobs": [...]}
            jobs = data.get('jobs', [])
            logger.info(f"Fetched {len(jobs)} jobs from Greenhouse for {self.board_token}")

            return jobs

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Greenhouse listings: {e}")
            return []

    def fetch_job_details(self, job_id: str) -> Dict:
        """Fetch full details for a single job."""
        url = self.get_job_detail_url(job_id)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching job {job_id}: {e}")
            return {}

    def standardize_job(self, raw_job: Dict) -> Dict:
        """Convert Greenhouse job format to standard format."""
        # Extract location
        location_parts = []
        if raw_job.get('location', {}).get('name'):
            location_parts.append(raw_job['location']['name'])

        # Greenhouse offices array
        offices = raw_job.get('offices', [])
        if offices and not location_parts:
            location_parts = [o.get('name', '') for o in offices if o.get('name')]

        location = ', '.join(location_parts) if location_parts else None

        # Extract department
        departments = raw_job.get('departments', [])
        department = departments[0].get('name') if departments else None

        # Build absolute URL
        job_id = raw_job.get('id')
        absolute_url = raw_job.get('absolute_url') or f"https://boards.greenhouse.io/{self.board_token}/jobs/{job_id}"

        # Detect company name from board info if not provided
        company_name = self.company_name
        if not company_name:
            # Try to get from API response or use board token
            company_name = raw_job.get('company', {}).get('name', self.board_token.title())

        return {
            'source_ats': self.ATS_NAME,
            'source_url': absolute_url,
            'external_requisition_id': str(job_id) if job_id else None,
            'company_name': company_name,
            'title': raw_job.get('title', 'Untitled'),
            'description': raw_job.get('content', ''),  # HTML content
            'location': location,
            'job_type': self._map_job_type(raw_job.get('employment_type')),
            'remote_status': self._extract_remote_status(raw_job),
            'salary_min': None,  # Greenhouse rarely includes salary in API
            'salary_max': None,
            'salary_currency': 'USD',
            'department': department,
            'raw_data': raw_job,
        }

    def _extract_remote_status(self, job: Dict) -> Optional[str]:
        """Extract remote status from Greenhouse job."""
        # Check location name
        location = job.get('location', {})
        if isinstance(location, dict):
            loc_name = location.get('name', '').lower()
        else:
            loc_name = str(location).lower()

        title = job.get('title', '').lower()

        # Check for remote indicators
        if 'remote' in loc_name or 'remote' in title:
            if 'hybrid' in loc_name or 'hybrid' in title:
                return 'hybrid'
            return 'remote'

        return 'on_site'


def scrape_company(board_token: str, company_name: Optional[str] = None) -> List[Dict]:
    """
    Convenience function to scrape a Greenhouse job board.

    Args:
        board_token: The company's Greenhouse board token
        company_name: Optional company name

    Returns:
        List of standardized job dictionaries

    Example:
        jobs = scrape_company('stripe', 'Stripe')
    """
    scraper = GreenhouseScraper(board_token, company_name)
    return scraper.scrape_all()
