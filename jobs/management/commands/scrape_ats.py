"""
Management command to scrape jobs from ATS platforms.

Usage:
    # Scrape single company from Greenhouse
    python manage.py scrape_ats greenhouse stripe --company-name "Stripe"

    # Scrape single company from Lever
    python manage.py scrape_ats lever netflix --company-name "Netflix"

    # Scrape from a config file
    python manage.py scrape_ats --config companies.json

    # Dry run
    python manage.py scrape_ats greenhouse airbnb --dry-run

Config file format (companies.json):
{
    "companies": [
        {"ats": "greenhouse", "slug": "stripe", "name": "Stripe"},
        {"ats": "greenhouse", "slug": "airbnb", "name": "Airbnb"},
        {"ats": "lever", "slug": "netflix", "name": "Netflix"},
        {"ats": "lever", "slug": "twitch", "name": "Twitch"}
    ]
}
"""

import json
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import ScrapedJobListing, Company
from jobs.scrapers import GreenhouseScraper, LeverScraper


class Command(BaseCommand):
    help = 'Scrape job listings from ATS platforms (Greenhouse, Lever)'

    SCRAPERS = {
        'greenhouse': GreenhouseScraper,
        'lever': LeverScraper,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            'ats',
            nargs='?',
            choices=['greenhouse', 'lever'],
            help='ATS platform to scrape'
        )
        parser.add_argument(
            'company_slug',
            nargs='?',
            help='Company slug/board token on the ATS'
        )
        parser.add_argument(
            '--company-name',
            type=str,
            help='Human-readable company name'
        )
        parser.add_argument(
            '--config',
            type=str,
            help='Path to JSON config file with multiple companies'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview scrape without saving'
        )
        parser.add_argument(
            '--score',
            action='store_true',
            help='Run HAS scoring after scraping'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay between companies in seconds (default: 1.0)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        run_scoring = options['score']
        delay = options['delay']

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be saved"))

        # Determine companies to scrape
        if options['config']:
            companies = self._load_config(options['config'])
        elif options['ats'] and options['company_slug']:
            companies = [{
                'ats': options['ats'],
                'slug': options['company_slug'],
                'name': options['company_name'],
            }]
        else:
            self.stdout.write(self.style.ERROR(
                "Must provide either --config or ATS and company_slug arguments"
            ))
            return

        self.stdout.write(f"Scraping {len(companies)} companies...")

        total_created = 0
        total_updated = 0
        all_imported = []

        for i, company in enumerate(companies, 1):
            if i > 1:
                time.sleep(delay)

            created, updated, imported = self._scrape_company(
                company['ats'],
                company['slug'],
                company.get('name'),
                dry_run
            )
            total_created += created
            total_updated += updated
            all_imported.extend(imported)

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Scraping complete:"))
        self.stdout.write(f"  Companies: {len(companies)}")
        self.stdout.write(f"  Created: {total_created}")
        self.stdout.write(f"  Updated: {total_updated}")

        # Run scoring
        if run_scoring and not dry_run and all_imported:
            self.stdout.write("")
            self._run_scoring(all_imported)

    def _load_config(self, config_path):
        """Load companies from config file."""
        with open(config_path, 'r') as f:
            data = json.load(f)
        return data.get('companies', [])

    def _scrape_company(self, ats, slug, name, dry_run):
        """Scrape a single company."""
        self.stdout.write(f"\nScraping {name or slug} from {ats}...")

        scraper_class = self.SCRAPERS.get(ats)
        if not scraper_class:
            self.stdout.write(self.style.ERROR(f"Unknown ATS: {ats}"))
            return 0, 0, []

        try:
            scraper = scraper_class(slug, name)
            jobs = scraper.scrape_all()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Scrape error: {e}"))
            return 0, 0, []

        self.stdout.write(f"  Found {len(jobs)} jobs")

        if dry_run:
            for job in jobs[:5]:  # Preview first 5
                self.stdout.write(f"    - {job['title']} ({job['location'] or 'No location'})")
            if len(jobs) > 5:
                self.stdout.write(f"    ... and {len(jobs) - 5} more")
            return len(jobs), 0, []

        created = 0
        updated = 0
        imported = []

        for job in jobs:
            try:
                result, listing = self._save_job(job)
                if result == 'created':
                    created += 1
                    imported.append(listing)
                elif result == 'updated':
                    updated += 1
                    imported.append(listing)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Error saving {job['title']}: {e}"))

        self.stdout.write(f"  Created: {created}, Updated: {updated}")
        return created, updated, imported

    def _save_job(self, job_data):
        """Save or update a job listing."""
        source_url = job_data.get('source_url')
        if not source_url:
            raise ValueError("No source_url")

        # Check if exists
        existing = ScrapedJobListing.objects.filter(source_url=source_url).first()

        if existing:
            # Update last seen and check for changes
            existing.date_last_seen = timezone.now()

            # Check for description changes (potential repost)
            import hashlib
            new_hash = hashlib.sha256(job_data.get('description', '').encode()).hexdigest()
            if existing.description_hash and existing.description_hash != new_hash:
                existing.repost_count += 1
                existing.description = job_data.get('description', '')

            existing.save()
            return 'updated', existing

        # Create new
        company = None
        if job_data.get('company_name'):
            company, _ = Company.find_or_create(job_data['company_name'])

        # CharField fields need empty strings, not None
        listing = ScrapedJobListing.objects.create(
            source_ats=job_data.get('source_ats', 'other'),
            source_url=source_url,
            external_requisition_id=job_data.get('external_requisition_id') or '',
            company_name=job_data.get('company_name', 'Unknown'),
            company=company,
            title=job_data.get('title', 'Untitled'),
            description=job_data.get('description', ''),
            location=job_data.get('location') or '',
            job_type=job_data.get('job_type') or '',
            remote_status=job_data.get('remote_status') or '',
            salary_min=job_data.get('salary_min'),
            salary_max=job_data.get('salary_max'),
            salary_currency=job_data.get('salary_currency', 'USD'),
            department=job_data.get('department') or '',
            raw_data=job_data.get('raw_data', {}),
            status='active'
        )
        return 'created', listing

    def _run_scoring(self, listings):
        """Run HAS scoring on scraped listings."""
        from jobs.scoring import HASEngine

        self.stdout.write("Running HAS scoring...")
        engine = HASEngine()
        scored = 0
        published = 0

        for listing in listings:
            try:
                has_score = engine.score_listing(listing, save=True)
                scored += 1
                if has_score.listing.published_to_board:
                    published += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Scoring error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Scored {scored} listings, {published} published to board"))
