"""
Backfill AI-generated description_summary on published ScrapedJobListing rows.

Generation used to happen on first pageview, which let bot crawls trigger
thousands of synchronous Anthropic calls and OOM the worker. This command
runs offline and can be capped via --limit to control per-run cost.

Usage:
    python manage.py backfill_summaries --limit 100
    python manage.py backfill_summaries --limit 100 --dry-run
    python manage.py backfill_summaries --all
"""

from django.core.management.base import BaseCommand

from jobs.models import ScrapedJobListing
from jobs.utils import generate_listing_summary


class Command(BaseCommand):
    help = 'Generate missing AI summaries for published observed listings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum listings to process this run (default: 100, ignored with --all)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process every eligible listing, ignoring --limit',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without calling Anthropic',
        )

    def handle(self, *args, **options):
        qs = (
            ScrapedJobListing.objects
            .filter(
                published_to_board=True,
                status='active',
                description_summary='',
            )
            .exclude(description='')
            .order_by('-date_first_seen')
        )

        # Listings with very short descriptions yield no useful summary;
        # generate_listing_summary already short-circuits below 100 chars,
        # but pre-filter so --limit isn't wasted on those rows.
        qs = qs.extra(where=["LENGTH(description) >= 500"])

        total = qs.count()
        self.stdout.write(f"Eligible listings missing summary: {total}")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - no Anthropic calls'))
            for listing in qs[:10]:
                self.stdout.write(f"  [{listing.id}] {listing.title} @ {listing.company_name}")
            return

        if not options['all']:
            qs = qs[:options['limit']]

        generated = 0
        skipped = 0
        for listing in qs.iterator():
            summary = generate_listing_summary(listing)
            if summary:
                generated += 1
            else:
                skipped += 1
            if (generated + skipped) % 25 == 0:
                self.stdout.write(f"  Processed {generated + skipped} ({generated} ok, {skipped} skipped)")

        self.stdout.write(self.style.SUCCESS(
            f"Backfill complete: {generated} summaries generated, {skipped} skipped"
        ))
