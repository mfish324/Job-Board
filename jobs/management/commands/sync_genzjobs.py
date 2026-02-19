"""
Sync job listings from genzjobs shared database to RJRP local tracker.

Pulls active listings from genzjobs PostgreSQL, creates/updates local
ScrapedJobListing records, and optionally writes verification status back.

Usage:
    python manage.py sync_genzjobs
    python manage.py sync_genzjobs --dry-run
    python manage.py sync_genzjobs --source greenhouse
    python manage.py sync_genzjobs --since 2024-01-01
    python manage.py sync_genzjobs --write-back
    python manage.py sync_genzjobs --score
"""

import hashlib
import re
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import (
    Company, GenzjobsListing, ScrapedJobListing, HiringActivityScore,
)


# Map genzjobs source names to ScrapedJobListing SOURCE_ATS_CHOICES
SOURCE_MAP = {
    'greenhouse': 'greenhouse',
    'lever': 'lever',
    'ashby': 'ashby',
    'smartrecruiters': 'smartrecruiters',
    'workday': 'workday',
    'icims': 'icims',
    'bamboohr': 'bamboohr',
    'jobvite': 'jobvite',
    'taleo': 'taleo',
    'remotive': 'remotive',
    'usajobs': 'usajobs',
    'jsearch': 'jsearch',
    'arbeitnow': 'arbeitnow',
    'jobicy': 'jobicy',
    'whoishiring': 'whoishiring',
}


class Command(BaseCommand):
    help = 'Sync job listings from genzjobs database to local RJRP tracker'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be synced without making changes',
        )
        parser.add_argument(
            '--source',
            type=str,
            help='Only sync listings from this source (e.g., greenhouse, lever)',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Only sync listings from this company name',
        )
        parser.add_argument(
            '--since',
            type=str,
            help='Only sync listings updated since this date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Number of listings to process per batch (default: 500)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximum number of listings to sync (0 = unlimited)',
        )
        parser.add_argument(
            '--score',
            action='store_true',
            help='Run HAS scoring on synced listings after import',
        )
        parser.add_argument(
            '--write-back',
            action='store_true',
            help='Write RJRP verification status back to genzjobs database',
        )

    def handle(self, *args, **options):
        if not settings.GENZJOBS_ENABLED:
            self.stderr.write(self.style.ERROR(
                'GENZJOBS_DATABASE_URL is not configured. Set it in your environment.'
            ))
            return

        dry_run = options['dry_run']
        score_after = options['score']
        write_back = options['write_back']
        batch_size = options['batch_size']

        if write_back:
            self._write_back(dry_run)
            return

        # Build queryset from genzjobs
        qs = GenzjobsListing.objects.filter(is_active=True)

        if options['source']:
            qs = qs.filter(source__icontains=options['source'])

        if options['company']:
            qs = qs.filter(company__icontains=options['company'])

        if options['since']:
            qs = qs.filter(updated_at__gte=options['since'])

        limit = options['limit']

        total = qs.count()
        self.stdout.write(f"Found {total} active listings in genzjobs")

        if limit:
            self.stdout.write(f"Limiting to {limit} listings")
            qs = qs[:limit]
            total = min(total, limit)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made'))
            # Show sample
            for gj in qs[:10]:
                self.stdout.write(f"  [{gj.source}] {gj.title} at {gj.company}")
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            return

        created = 0
        updated = 0
        errors = 0

        for gj in qs.iterator(chunk_size=batch_size):
            try:
                was_created = self._sync_listing(gj)
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(
                    f"Error syncing {gj.id} ({gj.title}): {e}"
                ))

            if (created + updated) % 100 == 0 and (created + updated) > 0:
                self.stdout.write(f"  Progress: {created + updated}/{total}")

        self.stdout.write(self.style.SUCCESS(
            f"Sync complete: {created} created, {updated} updated, {errors} errors"
        ))

        # Detect stale/closed listings
        self._detect_closed(qs)

        # Optionally score
        if score_after:
            self._score_synced()

    def _sync_listing(self, gj):
        """
        Sync a single genzjobs listing to local ScrapedJobListing.
        Returns True if created, False if updated.
        """
        now = timezone.now()

        # Map source
        source_ats = SOURCE_MAP.get(
            (gj.source or '').lower(),
            'other'
        )

        # Find or create local tracker
        try:
            local = ScrapedJobListing.objects.get(genzjobs_id=gj.id)
            was_created = False
        except ScrapedJobListing.DoesNotExist:
            local = ScrapedJobListing(genzjobs_id=gj.id)
            was_created = True

        # Cache display fields
        local.title = (gj.title or '')[:300]
        local.company_name = (gj.company or '')[:255]
        local.description = gj.description or ''
        local.location = (gj.location or '')[:200]
        local.source_ats = source_ats
        local.source_url = (gj.apply_url or gj.source_url or '')[:500]

        # Salary
        if gj.salary_min is not None:
            local.salary_min = gj.salary_min
        if gj.salary_max is not None:
            local.salary_max = gj.salary_max
        if gj.salary_currency:
            local.salary_currency = gj.salary_currency[:3]

        # Classification
        local.job_type = (gj.job_type or '')[:50]
        local.experience_level = (gj.experience_level or '')[:50]
        local.remote_status = 'remote' if gj.remote else ''
        local.job_category = self._map_category(gj.category)

        # Scoring-relevant enrichment fields
        local.has_requirements = bool(gj.requirements)
        local.has_benefits = bool(gj.benefits)
        local.has_company_logo = bool(gj.company_logo)
        local.has_company_website = bool(gj.company_website)
        local.classification_confidence = gj.classification_confidence
        local.publisher = (gj.publisher or '')[:100]

        # Skills count
        skills = self._parse_pg_array(gj.skills)
        local.skills_count = len(skills) if skills else 0

        # External ID
        if gj.source_id:
            local.external_requisition_id = gj.source_id[:100]

        # Tracking dates
        if gj.posted_at:
            local.date_posted_external = gj.posted_at
        local.date_last_seen = now
        if was_created and gj.created_at:
            # Preserve original first-seen from genzjobs
            local.date_first_seen = gj.created_at

        # Status
        local.status = 'active'

        # Find or create Company
        if local.company_name:
            company, _ = Company.find_or_create(local.company_name)
            local.company = company

        # Store genzjobs rich data in raw_data for template use
        raw = {}
        if gj.requirements:
            raw['requirements'] = gj.requirements
        if gj.benefits:
            raw['benefits'] = gj.benefits
        if skills:
            raw['skills'] = skills
        if gj.company_logo:
            raw['company_logo'] = gj.company_logo
        if gj.company_website:
            raw['company_website'] = gj.company_website
        audience_tags = self._parse_pg_array(gj.audience_tags)
        if audience_tags:
            raw['audience_tags'] = audience_tags
        local.raw_data = raw

        local.save()
        return was_created

    def _parse_pg_array(self, value):
        """Parse a PostgreSQL text[] array into a Python list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Handle Postgres array literal: {foo,bar,baz}
            s = value.strip()
            if s.startswith('{') and s.endswith('}'):
                inner = s[1:-1]
                if not inner:
                    return []
                return [item.strip().strip('"') for item in inner.split(',')]
            # Try JSON parse as fallback
            import json
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        return []

    def _map_category(self, category):
        """Map genzjobs category string to ScrapedJobListing JOB_CATEGORY_CHOICES."""
        if not category:
            return 'other'

        cat_lower = category.lower()
        mapping = {
            'engineering': 'engineering',
            'tech': 'engineering',
            'software': 'engineering',
            'healthcare': 'healthcare',
            'medical': 'healthcare',
            'retail': 'retail',
            'finance': 'finance',
            'accounting': 'finance',
            'sales': 'sales',
            'marketing': 'marketing',
            'operations': 'operations',
            'hr': 'hr',
            'human resources': 'hr',
            'legal': 'legal',
            'executive': 'executive',
            'management': 'executive',
        }

        for keyword, value in mapping.items():
            if keyword in cat_lower:
                return value
        return 'other'

    def _detect_closed(self, active_qs):
        """Mark local listings as closed if they're no longer active in genzjobs."""
        active_genzjobs_ids = set(active_qs.values_list('id', flat=True))

        # Find local listings with genzjobs_id that are NOT in the active set
        stale_locals = ScrapedJobListing.objects.filter(
            genzjobs_id__isnull=False,
            status='active',
        ).exclude(
            genzjobs_id__in=active_genzjobs_ids
        )

        # Check if they're actually inactive in genzjobs
        closed_count = 0
        for local in stale_locals.iterator():
            try:
                gj = GenzjobsListing.objects.get(id=local.genzjobs_id)
                if not gj.is_active:
                    local.status = 'closed'
                    local.date_removed = timezone.now()
                    local.save(update_fields=['status', 'date_removed'])
                    closed_count += 1
            except GenzjobsListing.DoesNotExist:
                # Listing removed from genzjobs entirely
                local.status = 'closed'
                local.date_removed = timezone.now()
                local.save(update_fields=['status', 'date_removed'])
                closed_count += 1

        if closed_count:
            self.stdout.write(f"Marked {closed_count} listings as closed")

    def _score_synced(self):
        """Run HAS scoring on recently synced listings."""
        from jobs.scoring.engine import HASEngine

        engine = HASEngine()
        recent = ScrapedJobListing.objects.filter(
            genzjobs_id__isnull=False,
            status='active',
        )

        total = recent.count()
        self.stdout.write(f"Scoring {total} synced listings...")

        scored = 0
        for processed, total_count, listing in engine.bulk_score(recent):
            scored = processed
            if processed % 100 == 0:
                self.stdout.write(f"  Scored {processed}/{total_count}")

        self.stdout.write(self.style.SUCCESS(f"Scored {scored} listings"))

    def _write_back(self, dry_run):
        """Write RJRP verification status back to genzjobs database."""
        # Find all local listings with genzjobs_id that have scores
        published = ScrapedJobListing.objects.filter(
            genzjobs_id__isnull=False,
            published_to_board=True,
        )

        unpublished = ScrapedJobListing.objects.filter(
            genzjobs_id__isnull=False,
            published_to_board=False,
        )

        pub_count = published.count()
        unpub_count = unpublished.count()

        self.stdout.write(
            f"Write-back: {pub_count} verified, {unpub_count} unverified"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made'))
            return

        written = 0
        errors = 0

        # Write verified status
        for local in published.iterator():
            try:
                gj = GenzjobsListing.objects.get(id=local.genzjobs_id)
                changed = False
                if not gj.is_rjrp_verified:
                    gj.is_rjrp_verified = True
                    changed = True
                # Write employer ID if listing is claimed
                if local.claimed_job and local.claimed_job.posted_by_id:
                    employer_id_str = str(local.claimed_job.posted_by_id)
                    if gj.rjrp_employer_id != employer_id_str:
                        gj.rjrp_employer_id = employer_id_str
                        changed = True
                if changed:
                    gj.save(update_fields=['is_rjrp_verified', 'rjrp_employer_id'])
                    written += 1
            except GenzjobsListing.DoesNotExist:
                errors += 1
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"Write-back error {local.genzjobs_id}: {e}"))

        # Clear verification for unpublished
        for local in unpublished.iterator():
            try:
                gj = GenzjobsListing.objects.get(id=local.genzjobs_id)
                if gj.is_rjrp_verified:
                    gj.is_rjrp_verified = False
                    gj.save(update_fields=['is_rjrp_verified'])
                    written += 1
            except GenzjobsListing.DoesNotExist:
                pass
            except Exception as e:
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f"Write-back complete: {written} updated, {errors} errors"
        ))
