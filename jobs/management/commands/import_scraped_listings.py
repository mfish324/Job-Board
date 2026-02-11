"""
Management command to import scraped job listings from JSON or CSV files.

Usage:
    python manage.py import_scraped_listings data.json
    python manage.py import_scraped_listings jobs.csv --format csv
    python manage.py import_scraped_listings data.json --dry-run
    python manage.py import_scraped_listings data.json --score  # Also run HAS scoring

Expected JSON format:
[
    {
        "source_ats": "greenhouse",
        "source_url": "https://boards.greenhouse.io/company/jobs/12345",
        "company_name": "Acme Corp",
        "title": "Software Engineer",
        "description": "Full job description here...",
        "location": "San Francisco, CA",
        "salary_min": 100000,
        "salary_max": 150000,
        "job_type": "full_time",
        "remote_status": "hybrid",
        "department": "Engineering"
    }
]

Expected CSV columns:
source_ats,source_url,company_name,title,description,location,salary_min,salary_max,job_type,remote_status,department
"""

import json
import csv
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import ScrapedJobListing, Company


class Command(BaseCommand):
    help = 'Import scraped job listings from JSON or CSV file'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to JSON or CSV file')
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv'],
            default='json',
            help='File format (default: json)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without saving'
        )
        parser.add_argument(
            '--score',
            action='store_true',
            help='Run HAS scoring after import'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing listings (matched by source_url)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        file_format = options['format']
        dry_run = options['dry_run']
        run_scoring = options['score']
        update_existing = options['update_existing']

        # Auto-detect format from extension
        if file_path.endswith('.csv'):
            file_format = 'csv'
        elif file_path.endswith('.json'):
            file_format = 'json'

        self.stdout.write(f"Importing from {file_path} (format: {file_format})")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be saved"))

        # Load data
        try:
            if file_format == 'json':
                listings_data = self._load_json(file_path)
            else:
                listings_data = self._load_csv(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading file: {e}"))
            return

        self.stdout.write(f"Found {len(listings_data)} listings to import")

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        imported_listings = []

        for i, data in enumerate(listings_data, 1):
            try:
                result = self._process_listing(data, dry_run, update_existing)
                if result == 'created':
                    created_count += 1
                    if not dry_run:
                        listing = ScrapedJobListing.objects.get(source_url=data['source_url'])
                        imported_listings.append(listing)
                elif result == 'updated':
                    updated_count += 1
                    if not dry_run:
                        listing = ScrapedJobListing.objects.get(source_url=data['source_url'])
                        imported_listings.append(listing)
                else:
                    skipped_count += 1

                if i % 100 == 0:
                    self.stdout.write(f"Processed {i}/{len(listings_data)}...")

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f"Error processing listing {i}: {data.get('title', 'Unknown')} - {e}"
                ))

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Import complete:"))
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Errors: {error_count}")

        # Run scoring if requested
        if run_scoring and not dry_run and imported_listings:
            self.stdout.write("")
            self.stdout.write("Running HAS scoring on imported listings...")
            self._run_scoring(imported_listings)

    def _load_json(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_csv(self, file_path):
        listings = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert empty strings to None for numeric fields
                for field in ['salary_min', 'salary_max']:
                    if field in row and row[field] == '':
                        row[field] = None
                    elif field in row and row[field]:
                        row[field] = float(row[field])
                listings.append(row)
        return listings

    def _process_listing(self, data, dry_run, update_existing):
        """Process a single listing. Returns 'created', 'updated', or 'skipped'."""
        source_url = data.get('source_url')
        if not source_url:
            raise ValueError("source_url is required")

        # Check if exists
        existing = ScrapedJobListing.objects.filter(source_url=source_url).first()

        if existing:
            if update_existing:
                if not dry_run:
                    self._update_listing(existing, data)
                return 'updated'
            else:
                return 'skipped'

        if dry_run:
            self.stdout.write(f"  Would create: {data.get('title')} at {data.get('company_name')}")
            return 'created'

        # Create new listing
        self._create_listing(data)
        return 'created'

    def _create_listing(self, data):
        """Create a new ScrapedJobListing."""
        # Find or create company
        company = None
        company_name = data.get('company_name')
        if company_name:
            company, _ = Company.find_or_create(company_name)

        # CharField fields need empty strings, not None
        listing = ScrapedJobListing.objects.create(
            source_ats=data.get('source_ats', 'other'),
            source_url=data['source_url'],
            external_requisition_id=data.get('external_requisition_id') or '',
            company_name=company_name or 'Unknown',
            company=company,
            title=data.get('title', 'Untitled'),
            description=data.get('description', ''),
            location=data.get('location') or '',
            job_type=data.get('job_type') or '',
            experience_level=data.get('experience_level') or '',
            remote_status=data.get('remote_status') or '',
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            salary_currency=data.get('salary_currency', 'USD'),
            department=data.get('department') or '',
            raw_data=data.get('raw_data', {}),
            status='active'
        )
        return listing

    def _update_listing(self, listing, data):
        """Update an existing listing with new data."""
        # Update date_last_seen
        listing.date_last_seen = timezone.now()

        # Check for description changes (potential repost)
        import hashlib
        new_desc_hash = hashlib.sha256(data.get('description', '').encode()).hexdigest()
        if listing.description_hash and listing.description_hash != new_desc_hash:
            listing.repost_count += 1

        # Update fields
        updateable_fields = [
            'title', 'description', 'location', 'job_type', 'experience_level',
            'remote_status', 'salary_min', 'salary_max', 'salary_currency', 'department'
        ]
        for field in updateable_fields:
            if field in data and data[field] is not None:
                setattr(listing, field, data[field])

        listing.save()

    def _run_scoring(self, listings):
        """Run HAS scoring on imported listings."""
        from jobs.scoring import HASEngine

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
                self.stdout.write(self.style.WARNING(f"  Scoring error for {listing.title}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Scored {scored} listings, {published} published to board"))
