"""
Management command to check if external source URLs for scraped listings are still live.

Makes HTTP HEAD requests against source_url for active/published listings.
If a URL returns 404, 410, or a connection error, the listing is marked as closed.

Usage:
    python manage.py check_listing_links                # Check all active listings
    python manage.py check_listing_links --dry-run      # Preview without changes
    python manage.py check_listing_links --batch 50     # Check 50 at a time
    python manage.py check_listing_links --timeout 10   # Custom timeout in seconds
"""

import requests
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import ScrapedJobListing


# HTTP status codes that indicate a dead listing
DEAD_STATUS_CODES = {404, 410, 403}

# Status codes that might be temporary — don't close these
TRANSIENT_CODES = {429, 500, 502, 503, 504}


class Command(BaseCommand):
    help = 'Check if external URLs for scraped listings are still live'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without making updates',
        )
        parser.add_argument(
            '--batch',
            type=int,
            default=100,
            help='Maximum number of listings to check per run (default: 100)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='HTTP request timeout in seconds (default: 15)',
        )
        parser.add_argument(
            '--recheck-days',
            type=int,
            default=1,
            help='Skip listings checked within this many days (default: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch']
        timeout = options['timeout']
        recheck_days = options['recheck_days']

        now = timezone.now()
        recheck_threshold = now - timedelta(days=recheck_days)

        # Get active/published listings, oldest-checked first
        listings = ScrapedJobListing.objects.filter(
            status__in=['active', 'published'],
            published_to_board=True,
        ).exclude(
            link_last_checked__gte=recheck_threshold,
        ).order_by('link_last_checked')[:batch_size]

        total = listings.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                'No listings need link checking right now.'
            ))
            return

        self.stdout.write(f'Checking {total} listing URL(s)...\n')

        dead_count = 0
        live_count = 0
        error_count = 0

        headers = {
            'User-Agent': 'RJRP-LinkChecker/1.0 (job board health check)',
            'Accept': 'text/html',
        }

        for listing in listings:
            url = listing.source_url
            try:
                # Use HEAD first, fall back to GET if HEAD is blocked
                resp = requests.head(
                    url, timeout=timeout, headers=headers,
                    allow_redirects=True
                )

                # Some servers block HEAD — retry with GET
                if resp.status_code == 405:
                    resp = requests.get(
                        url, timeout=timeout, headers=headers,
                        allow_redirects=True, stream=True
                    )
                    resp.close()

                if resp.status_code in DEAD_STATUS_CODES:
                    dead_count += 1
                    self._handle_dead(listing, resp.status_code, dry_run, now)
                elif resp.status_code in TRANSIENT_CODES:
                    error_count += 1
                    self.stdout.write(self.style.WARNING(
                        f'  TRANSIENT ({resp.status_code}): {listing.title} '
                        f'at {listing.company_name}'
                    ))
                    if not dry_run:
                        listing.link_last_checked = now
                        listing.save(update_fields=['link_last_checked'])
                else:
                    live_count += 1
                    if not dry_run:
                        listing.link_last_checked = now
                        listing.link_status_code = resp.status_code
                        listing.save(update_fields=[
                            'link_last_checked', 'link_status_code'
                        ])

            except requests.exceptions.Timeout:
                error_count += 1
                self.stdout.write(self.style.WARNING(
                    f'  TIMEOUT: {listing.title} at {listing.company_name}'
                ))
                if not dry_run:
                    listing.link_last_checked = now
                    listing.save(update_fields=['link_last_checked'])

            except requests.exceptions.ConnectionError:
                dead_count += 1
                self._handle_dead(listing, 0, dry_run, now)

            except requests.exceptions.RequestException as e:
                error_count += 1
                self.stdout.write(self.style.WARNING(
                    f'  ERROR: {listing.title} — {type(e).__name__}'
                ))
                if not dry_run:
                    listing.link_last_checked = now
                    listing.save(update_fields=['link_last_checked'])

        # Summary
        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Link check complete: '
            f'{live_count} live, {dead_count} dead, {error_count} errors '
            f'(out of {total} checked)'
        ))

    def _handle_dead(self, listing, status_code, dry_run, now):
        """Mark a listing as closed due to dead link."""
        label = f'HTTP {status_code}' if status_code else 'Connection failed'
        if dry_run:
            self.stdout.write(self.style.ERROR(
                f'  DEAD ({label}): {listing.title} at {listing.company_name} '
                f'— would close'
            ))
        else:
            listing.status = 'closed'
            listing.date_removed = now
            listing.published_to_board = False
            listing.link_last_checked = now
            listing.link_status_code = status_code
            listing.save(update_fields=[
                'status', 'date_removed', 'published_to_board',
                'link_last_checked', 'link_status_code',
            ])
            self.stdout.write(self.style.ERROR(
                f'  CLOSED ({label}): {listing.title} at {listing.company_name}'
            ))
