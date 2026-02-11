"""
Management command to update CompanyHiringProfile metrics.

This should be run daily, before score_listings, to ensure company-level
metrics are fresh when calculating individual listing scores.

Usage:
    python manage.py update_company_profiles           # Update all profiles
    python manage.py update_company_profiles --dry-run # Preview without saving
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q
from django.utils import timezone
from jobs.models import Company, CompanyHiringProfile, ScrapedJobListing


class Command(BaseCommand):
    help = 'Update CompanyHiringProfile metrics for all companies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Only update profile for a specific company name',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed metrics for each company',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        company_filter = options['company']
        verbose = options['verbose']

        # Get companies with scraped listings
        queryset = Company.objects.all()

        if company_filter:
            queryset = queryset.filter(name__icontains=company_filter)

        total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No companies to update.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would update {total} company profile(s)'
            ))
        else:
            self.stdout.write(f'Updating {total} company profile(s)...')

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)

        updated = 0
        created = 0

        for company in queryset:
            listings = company.scraped_listings.all()

            # Calculate metrics
            active_listings = listings.filter(status='active')
            total_active = active_listings.count()
            total_historical = listings.count()

            # Distinct departments
            departments = listings.values('department').distinct().count()

            # Average listing lifespan (for closed listings)
            closed_listings = listings.filter(
                status='closed',
                date_removed__isnull=False
            )
            if closed_listings.exists():
                lifespans = []
                for listing in closed_listings:
                    days = (listing.date_removed - listing.date_first_seen).days
                    if days >= 0:
                        lifespans.append(days)
                avg_lifespan = sum(lifespans) / len(lifespans) if lifespans else None
                median_lifespan = sorted(lifespans)[len(lifespans) // 2] if lifespans else None
            else:
                avg_lifespan = None
                median_lifespan = None

            # Close rate in last 30 days
            closed_30d = listings.filter(
                date_removed__gte=thirty_days_ago
            ).count()
            active_30d_ago = listings.filter(
                date_first_seen__lt=thirty_days_ago
            ).count()
            close_rate_30d = (closed_30d / active_30d_ago * 100) if active_30d_ago > 0 else None

            # Net job movement
            new_30d = listings.filter(date_first_seen__gte=thirty_days_ago).count()
            closed_30d = listings.filter(date_removed__gte=thirty_days_ago).count()
            net_30d = new_30d - closed_30d

            new_90d = listings.filter(date_first_seen__gte=ninety_days_ago).count()
            closed_90d = listings.filter(date_removed__gte=ninety_days_ago).count()
            net_90d = new_90d - closed_90d

            # Repost frequency
            total_reposts = listings.aggregate(total=Avg('repost_count'))['total'] or 0

            # Boilerplate ratio (simplified: % with same description hash)
            if total_historical > 1:
                hash_counts = listings.values('description_hash').annotate(
                    count=Count('id')
                ).filter(count__gt=1)
                duplicate_count = sum(h['count'] - 1 for h in hash_counts)
                boilerplate_ratio = duplicate_count / total_historical
            else:
                boilerplate_ratio = 0.0

            # Average description length
            avg_desc_len = listings.exclude(description='').extra(
                select={'desc_len': 'LENGTH(description)'}
            ).values_list('desc_len', flat=True)
            avg_description_length = (
                sum(avg_desc_len) // len(avg_desc_len) if avg_desc_len else 0
            )

            # Salary info ratio
            with_salary = listings.filter(
                Q(salary_min__isnull=False) | Q(salary_max__isnull=False)
            ).count()
            salary_ratio = with_salary / total_historical if total_historical > 0 else 0

            # Evergreen listings (open 90+ days, no changes)
            evergreen_count = active_listings.filter(
                date_first_seen__lt=ninety_days_ago,
                repost_count=0
            ).count()

            # Calculate reputation score (simplified algorithm)
            reputation = 50.0  # Base

            # Positive factors
            if avg_lifespan and avg_lifespan < 45:
                reputation += 10  # Fast hiring cycle
            if close_rate_30d and close_rate_30d > 20:
                reputation += 10  # Actively filling roles
            if net_30d > 0:
                reputation += min(net_30d * 2, 10)  # Growing
            if salary_ratio > 0.5:
                reputation += 5  # Transparent about salary

            # Negative factors
            if evergreen_count > 3:
                reputation -= min(evergreen_count * 2, 15)  # Too many stale listings
            if boilerplate_ratio > 0.5:
                reputation -= 10  # Copy-paste job postings

            reputation = max(0, min(100, reputation))

            # Get or create profile
            profile, is_created = CompanyHiringProfile.objects.get_or_create(
                company=company
            )

            if verbose:
                self.stdout.write(f'\n{company.name}:')
                self.stdout.write(f'  Active listings: {total_active}')
                self.stdout.write(f'  Historical listings: {total_historical}')
                self.stdout.write(f'  Departments: {departments}')
                self.stdout.write(f'  Avg lifespan: {avg_lifespan:.1f} days' if avg_lifespan else '  Avg lifespan: N/A')
                self.stdout.write(f'  Net movement (30d): {net_30d:+d}')
                self.stdout.write(f'  Net movement (90d): {net_90d:+d}')
                self.stdout.write(f'  Boilerplate ratio: {boilerplate_ratio:.1%}')
                self.stdout.write(f'  Evergreen count: {evergreen_count}')
                self.stdout.write(f'  Reputation score: {reputation:.1f}')
            else:
                status = 'created' if is_created else 'updated'
                self.stdout.write(
                    f'  {company.name}: {total_active} active, rep={reputation:.0f} ({status})'
                )

            if not dry_run:
                profile.total_active_listings = total_active
                profile.total_historical_listings = total_historical
                profile.total_distinct_departments = departments
                profile.avg_listing_lifespan_days = avg_lifespan
                profile.median_listing_lifespan_days = median_lifespan
                profile.listing_close_rate_30d = close_rate_30d
                profile.net_job_movement_30d = net_30d
                profile.net_job_movement_90d = net_90d
                profile.repost_frequency = total_reposts
                profile.boilerplate_ratio = boilerplate_ratio
                profile.avg_description_length = avg_description_length
                profile.has_salary_info_ratio = salary_ratio
                profile.evergreen_listing_count = evergreen_count
                profile.reputation_score = reputation
                profile.save()

                if is_created:
                    created += 1
                else:
                    updated += 1

        # Summary
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would create {created} and update {updated} profile(s).'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Created {created} and updated {updated} company profile(s).'
            ))
