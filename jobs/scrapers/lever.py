"""
Lever ATS scraper.

Lever provides a public JSON API for job postings:
https://api.lever.co/v0/postings/{company}

Example:
    scraper = LeverScraper('netflix')  # For jobs.lever.co/netflix
    jobs = scraper.scrape_all()
"""

import requests
import logging
from typing import List, Dict, Optional
from .base import BaseScraper

logger = logging.getLogger(__name__)


class LeverScraper(BaseScraper):
    """Scraper for Lever job boards."""

    ATS_NAME = 'lever'
    BASE_URL = 'https://api.lever.co/v0/postings'

    def __init__(self, company_slug: str, company_name: Optional[str] = None):
        """
        Initialize Lever scraper.

        Args:
            company_slug: The company's Lever slug (e.g., 'netflix', 'twitch')
            company_name: Human-readable company name
        """
        super().__init__(company_slug, company_name)
        self.company_slug = company_slug

    def get_job_list_url(self) -> str:
        return f"{self.BASE_URL}/{self.company_slug}"

    def get_job_detail_url(self, job_id: str) -> str:
        return f"{self.BASE_URL}/{self.company_slug}/{job_id}"

    def fetch_listings(self) -> List[Dict]:
        """Fetch all job listings from Lever API."""
        url = self.get_job_list_url()
        params = {'mode': 'json'}

        all_jobs = []
        offset = 0
        limit = 100  # Lever's max per page

        try:
            while True:
                params['offset'] = offset
                params['limit'] = limit

                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                jobs = response.json()

                if not jobs:
                    break

                all_jobs.extend(jobs)
                logger.debug(f"Fetched {len(jobs)} jobs (total: {len(all_jobs)})")

                if len(jobs) < limit:
                    break

                offset += limit

            logger.info(f"Fetched {len(all_jobs)} jobs from Lever for {self.company_slug}")
            return all_jobs

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Lever listings: {e}")
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
        """Convert Lever job format to standard format."""
        # Extract location
        location = raw_job.get('workplaceType')
        if location == 'unspecified':
            location = None

        # Lever categories contain team/department/location info
        categories = raw_job.get('categories', {})

        # Location from categories if not in workplaceType
        if not location:
            location = categories.get('location')

        # Department/team
        department = categories.get('team') or categories.get('department')

        # Commitment (full-time, part-time, etc.)
        commitment = categories.get('commitment', '').lower()
        job_type = self._map_job_type(commitment)

        # Work type (on-site, remote, hybrid)
        workplace_type = raw_job.get('workplaceType', '').lower()
        if workplace_type == 'remote':
            remote_status = 'remote'
        elif workplace_type == 'hybrid':
            remote_status = 'hybrid'
        elif workplace_type == 'on-site' or workplace_type == 'onsite':
            remote_status = 'on_site'
        else:
            remote_status = self._extract_remote_status(raw_job)

        # Build description from parts
        description = raw_job.get('descriptionPlain', '')
        if not description:
            # Try HTML version
            description = raw_job.get('description', '')

        # Add lists (requirements, responsibilities, etc.)
        lists = raw_job.get('lists', [])
        for lst in lists:
            list_text = lst.get('text', '')
            list_content = lst.get('content', '')
            if list_text or list_content:
                description += f"\n\n{list_text}\n{list_content}"

        # Salary info (Lever sometimes includes this)
        salary_range = raw_job.get('salaryRange', {})
        salary_min = salary_range.get('min')
        salary_max = salary_range.get('max')
        salary_currency = salary_range.get('currency', 'USD')

        # Company name
        company_name = self.company_name or self.company_slug.replace('-', ' ').title()

        return {
            'source_ats': self.ATS_NAME,
            'source_url': raw_job.get('hostedUrl', ''),
            'external_requisition_id': raw_job.get('id'),
            'company_name': company_name,
            'title': raw_job.get('text', 'Untitled'),
            'description': description,
            'location': location,
            'job_type': job_type,
            'remote_status': remote_status,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_currency': salary_currency,
            'department': department,
            'raw_data': raw_job,
        }


def scrape_company(company_slug: str, company_name: Optional[str] = None) -> List[Dict]:
    """
    Convenience function to scrape a Lever job board.

    Args:
        company_slug: The company's Lever slug
        company_name: Optional company name

    Returns:
        List of standardized job dictionaries

    Example:
        jobs = scrape_company('netflix', 'Netflix')
    """
    scraper = LeverScraper(company_slug, company_name)
    return scraper.scrape_all()
