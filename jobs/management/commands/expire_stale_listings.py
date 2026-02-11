"""
Management command to mark scraped listings as stale if not seen recently.

A listing is considered stale if it hasn't been seen by the scraper
in a configurable number of days (default: 7).

Usage:
    python manage.py expire_stale_listings              # Mark stale listings
    python manage.py expire_stale_listings --dry-run   # Preview without changes
    python manage.py expire_stale_listings --days 14   # Custom threshold
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import ScrapedJobListing


class Command(BaseCommand):
    help = 'Mark scraped job listings as stale if not seen recently'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be marked stale without making changes',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days since last seen to consider stale (default: 7)',
        )
        parser.add_argument(
            '--close-after',
            type=int,
            default=30,
            help='Mark as closed (not just stale) after this many days (default: 30)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        stale_days = options['days']
        close_days = options['close_after']

        now = timezone.now()
        stale_threshold = now - timedelta(days=stale_days)
        close_threshold = now - timedelta(days=close_days)

        # Find active listings not seen since threshold
        stale_listings = ScrapedJobListing.objects.filter(
            status='active',
            date_last_seen__lt=stale_threshold,
            date_last_seen__gte=close_threshold
        )

        # Find listings that should be marked closed
        closed_listings = ScrapedJobListing.objects.filter(
            status__in=['active', 'stale'],
            date_last_seen__lt=close_threshold
        )

        stale_count = stale_listings.count()
        close_count = closed_listings.count()

        if stale_count == 0 and close_count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'No listings to update (threshold: {stale_days} days stale, {close_days} days closed).'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would mark {stale_count} listing(s) as stale '
                f'and {close_count} listing(s) as closed'
            ))

            if stale_count > 0:
                self.stdout.write('\nListings to mark STALE:')
                for listing in stale_listings[:20]:
                    days_ago = (now - listing.date_last_seen).days
                    self.stdout.write(
                        f'  - {listing.title} at {listing.company_name} '
                        f'(last seen: {days_ago} days ago)'
                    )
                if stale_count > 20:
                    self.stdout.write(f'  ... and {stale_count - 20} more')

            if close_count > 0:
                self.stdout.write('\nListings to mark CLOSED:')
                for listing in closed_listings[:20]:
                    days_ago = (now - listing.date_last_seen).days
                    self.stdout.write(
                        f'  - {listing.title} at {listing.company_name} '
                        f'(last seen: {days_ago} days ago)'
                    )
                if close_count > 20:
                    self.stdout.write(f'  ... and {close_count - 20} more')
        else:
            # Mark stale listings
            if stale_count > 0:
                stale_listings.update(status='stale')
                self.stdout.write(self.style.SUCCESS(
                    f'Marked {stale_count} listing(s) as stale.'
                ))

            # Mark closed listings and set date_removed
            if close_count > 0:
                for listing in closed_listings:
                    listing.status = 'closed'
                    listing.date_removed = now
                    listing.published_to_board = False  # Unpublish closed listings
                    listing.save()

                self.stdout.write(self.style.SUCCESS(
                    f'Marked {close_count} listing(s) as closed.'
                ))

        # Summary statistics
        self.stdout.write('')
        total_active = ScrapedJobListing.objects.filter(status='active').count()
        total_stale = ScrapedJobListing.objects.filter(status='stale').count()
        total_closed = ScrapedJobListing.objects.filter(status='closed').count()
        total_published = ScrapedJobListing.objects.filter(status='published').count()

        self.stdout.write('Current listing status counts:')
        self.stdout.write(f'  Active: {total_active}')
        self.stdout.write(f'  Stale: {total_stale}')
        self.stdout.write(f'  Closed: {total_closed}')
        self.stdout.write(f'  Published: {total_published}')
