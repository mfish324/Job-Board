"""
Management command to check if employer career portal URLs are still reachable.

Checks both the base career_url and a sample deep-link (with a generic query)
for each active FeaturedEmployer. Tracks consecutive failures and marks
employers as unhealthy after repeated failures.

Usage:
    python manage.py check_directory_links                  # Check all active employers
    python manage.py check_directory_links --dry-run        # Preview without changes
    python manage.py check_directory_links --employer google  # Check one employer by slug
    python manage.py check_directory_links --timeout 20     # Custom timeout
    python manage.py check_directory_links --failure-threshold 5  # Failures before unhealthy
"""

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from directory.models import FeaturedEmployer
from directory.utils import build_deep_link


# Definite failures
DEAD_STATUS_CODES = {404, 410}

# Likely blocking our checker or SPA returning non-standard codes — not a real failure
BLOCKED_STATUS_CODES = {400, 403, 406, 429}

# Transient server errors — don't count as failure
TRANSIENT_CODES = {500, 502, 503, 504}

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


class Command(BaseCommand):
    help = 'Check health of employer career portal URLs in the directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show results without updating the database',
        )
        parser.add_argument(
            '--employer',
            type=str,
            help='Check only this employer (by slug)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='HTTP request timeout in seconds (default: 15)',
        )
        parser.add_argument(
            '--failure-threshold',
            type=int,
            default=3,
            help='Consecutive failures before marking unhealthy (default: 3)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        timeout = options['timeout']
        threshold = options['failure_threshold']
        now = timezone.now()

        employers = FeaturedEmployer.objects.filter(is_active=True)
        if options['employer']:
            employers = employers.filter(slug=options['employer'])

        total = employers.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No matching employers found.'))
            return

        self.stdout.write(f'Checking {total} employer career portal(s)...\n')

        healthy = 0
        degraded = 0
        dead = 0
        errors = 0

        for employer in employers:
            base_ok = self._check_url(employer.career_url, timeout, 'base')
            deep_link = build_deep_link(employer, query='software engineer')
            deep_ok = self._check_url(deep_link, timeout, 'deep-link')

            # Determine overall health for this employer
            if base_ok and deep_ok:
                status = 'healthy'
                status_label = self.style.SUCCESS('HEALTHY')
                healthy += 1
            elif base_ok and deep_ok is None:
                # Base works, deep-link had transient/blocked issue
                status = 'healthy'
                status_label = self.style.SUCCESS('HEALTHY (deep-link inconclusive)')
                healthy += 1
            elif base_ok and not deep_ok:
                status = 'degraded'
                status_label = self.style.WARNING('DEGRADED (deep-link broken)')
                degraded += 1
            elif base_ok is None:
                # Transient/blocked on base URL
                status = 'inconclusive'
                status_label = self.style.WARNING('INCONCLUSIVE (blocked/transient)')
                errors += 1
            else:
                status = 'dead'
                status_label = self.style.ERROR('DOWN')
                dead += 1

            self.stdout.write(f'  {status_label}: {employer.name} — {employer.career_url}')

            if dry_run:
                continue

            # Update employer record
            if status == 'healthy':
                employer.link_consecutive_failures = 0
                employer.link_healthy = True
                employer.link_status_code = 200
            elif status == 'degraded':
                employer.link_consecutive_failures += 1
                if employer.link_consecutive_failures >= threshold:
                    employer.link_healthy = False
                    self.stdout.write(self.style.ERROR(
                        f'    ^ Marked UNHEALTHY after {employer.link_consecutive_failures} '
                        f'consecutive failures'
                    ))
            elif status == 'dead':
                employer.link_consecutive_failures += 1
                if employer.link_consecutive_failures >= threshold:
                    employer.link_healthy = False
                    self.stdout.write(self.style.ERROR(
                        f'    ^ Marked UNHEALTHY after {employer.link_consecutive_failures} '
                        f'consecutive failures'
                    ))
            # 'inconclusive' — don't increment or reset failures

            employer.link_last_checked = now
            employer.save(update_fields=[
                'link_last_checked', 'link_status_code',
                'link_consecutive_failures', 'link_healthy',
            ])

        # Summary
        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Directory link check complete: '
            f'{healthy} healthy, {degraded} degraded, {dead} down, '
            f'{errors} inconclusive (out of {total} checked)'
        ))

    def _check_url(self, url, timeout, label):
        """
        Check a single URL. Returns:
            True  — URL is reachable (2xx or 3xx)
            False — URL is dead (404, 410, connection error)
            None  — Inconclusive (blocked, transient error)
        """
        try:
            resp = requests.get(
                url, timeout=timeout, headers=HEADERS,
                allow_redirects=True, stream=True,
            )
            resp.close()

            if resp.status_code < 400:
                return True
            elif resp.status_code in DEAD_STATUS_CODES:
                self.stdout.write(self.style.ERROR(
                    f'    {label}: HTTP {resp.status_code}'
                ))
                return False
            elif resp.status_code in BLOCKED_STATUS_CODES:
                self.stdout.write(self.style.WARNING(
                    f'    {label}: HTTP {resp.status_code} (likely bot-blocked)'
                ))
                return None
            elif resp.status_code in TRANSIENT_CODES:
                self.stdout.write(self.style.WARNING(
                    f'    {label}: HTTP {resp.status_code} (transient)'
                ))
                return None
            else:
                self.stdout.write(self.style.WARNING(
                    f'    {label}: HTTP {resp.status_code}'
                ))
                return False

        except requests.exceptions.Timeout:
            self.stdout.write(self.style.WARNING(
                f'    {label}: TIMEOUT'
            ))
            return None

        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR(
                f'    {label}: CONNECTION ERROR'
            ))
            return False

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.WARNING(
                f'    {label}: {type(e).__name__}'
            ))
            return None
