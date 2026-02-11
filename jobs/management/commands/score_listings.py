"""
Management command to calculate Hiring Activity Scores for scraped job listings.

Usage:
    python manage.py score_listings              # Score all active listings
    python manage.py score_listings --dry-run   # Preview without saving
    python manage.py score_listings --company "Acme Corp"  # Score specific company
    python manage.py score_listings --verbose   # Show detailed breakdown
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from jobs.models import ScrapedJobListing
from jobs.scoring import HASEngine


class Command(BaseCommand):
    help = 'Calculate Hiring Activity Scores for scraped job listings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show scores without saving to database',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Only score listings for a specific company name',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed score breakdown for each listing',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-score listings even if they already have a score',
        )
        parser.add_argument(
            '--min-score',
            type=int,
            default=0,
            help='Only show listings with score at or above this threshold',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        company_filter = options['company']
        verbose = options['verbose']
        force = options['force']
        min_score = options['min_score']

        # Build queryset
        queryset = ScrapedJobListing.objects.filter(
            Q(status='active') | Q(status='published')
        )

        if company_filter:
            queryset = queryset.filter(company_name__icontains=company_filter)

        if not force:
            # Only score listings without a score
            queryset = queryset.filter(activity_score__isnull=True)

        total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                'No listings to score. Use --force to re-score existing listings.'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would score {total} listing(s)'
            ))
        else:
            self.stdout.write(f'Scoring {total} listing(s)...')

        engine = HASEngine()
        scored = 0
        published = 0
        by_band = {'very_active': 0, 'likely_active': 0, 'uncertain': 0, 'low_signal': 0}

        for listing in queryset.select_related('company'):
            score, breakdown = engine.calculate_score(listing)
            band = engine.get_score_band(score)

            # Track statistics
            by_band[band] += 1
            if score >= min_score:
                scored += 1
                if engine.should_publish(score):
                    published += 1

            # Skip if below minimum score threshold (for display)
            if score < min_score:
                continue

            if verbose:
                self.stdout.write(f'\n{listing.title} ({listing.company_name})')
                self.stdout.write(f'  Score: {score} ({band})')
                self.stdout.write('  Breakdown:')
                for signal_name, signal_data in breakdown.items():
                    points = signal_data['points']
                    explanation = signal_data['explanation']
                    if points != 0 or signal_name == 'base':
                        prefix = '+' if points > 0 else ''
                        self.stdout.write(f'    {signal_name}: {prefix}{points} ({explanation})')
            else:
                marker = '*' if engine.should_publish(score) else ' '
                self.stdout.write(f'  {marker} [{score:3d}] {band:14s} - {listing.title[:40]}')

            if not dry_run:
                engine.score_listing(listing, save=True)

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'Total scored: {scored}')
        self.stdout.write(f'Would publish: {published}')
        self.stdout.write('')
        self.stdout.write('Distribution by band:')
        for band, count in by_band.items():
            self.stdout.write(f'  {band}: {count}')

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '[DRY RUN] No changes saved. Remove --dry-run to save scores.'
            ))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'Successfully scored {scored} listing(s).'
            ))
