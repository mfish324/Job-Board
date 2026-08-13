"""
Backfill salary_min/salary_max by parsing description text.

Direct-ATS feeds omit structured salary even when the listing text contains a
legally-mandated pay-transparency range. This command runs the conservative
extractor in jobs/salary_extract.py over listings that have a description but
no structured salary, and populates the fields.

Usage:
    python manage.py extract_salaries --dry-run          # count + samples, no writes
    python manage.py extract_salaries                    # backfill published listings
    python manage.py extract_salaries --all-statuses     # include unpublished/stale
    python manage.py extract_salaries --limit 500

After a real run, scores pick up the new salary signal at the next daily
rescore (score_listings --force, the RJRP-daily-rescore cron). Run it
manually if you want the HAS changes immediately.
"""

from django.core.management.base import BaseCommand

from jobs.models import ScrapedJobListing
from jobs.salary_extract import extract_salary_range


class Command(BaseCommand):
    help = 'Parse salary ranges out of description text into salary_min/salary_max'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be extracted without writing')
        parser.add_argument('--limit', type=int, default=0,
                            help='Stop after scanning this many listings (0 = all)')
        parser.add_argument('--all-statuses', action='store_true',
                            help='Include unpublished/stale/closed listings '
                                 '(default: published active listings only)')
        parser.add_argument('--samples', type=int, default=10,
                            help='How many example extractions to print')

    def handle(self, *args, **options):
        qs = ScrapedJobListing.objects.filter(
            salary_min__isnull=True, salary_max__isnull=True,
        ).exclude(description='')
        if not options['all_statuses']:
            qs = qs.filter(published_to_board=True, status__in=['active', 'published'])

        # only(): save() recomputes description/title hashes, so those source
        # fields must be loaded or every save triggers deferred-field queries.
        qs = qs.only('id', 'title', 'company_name', 'description',
                     'salary_min', 'salary_max', 'date_last_seen')
        if options['limit']:
            qs = qs[:options['limit']]

        scanned = extracted = 0
        samples = []
        for listing in qs.iterator(chunk_size=500):
            scanned += 1
            result = extract_salary_range(listing.description)
            if not result:
                continue
            lo, hi = result
            extracted += 1
            if len(samples) < options['samples']:
                samples.append(
                    f'  {listing.company_name[:28]:30s} {listing.title[:44]:46s} '
                    f'{lo if lo is not None else "—"} .. {hi if hi is not None else "—"}'
                )
            if not options['dry_run']:
                listing.salary_min = lo
                listing.salary_max = hi
                listing.save(update_fields=['salary_min', 'salary_max'])
            if scanned % 2000 == 0:
                self.stdout.write(f'  ...scanned {scanned}, extracted {extracted}')

        mode = 'DRY RUN — no writes' if options['dry_run'] else 'written'
        self.stdout.write(self.style.SUCCESS(
            f'Scanned {scanned} listings without structured salary; '
            f'extracted salary for {extracted} '
            f'({100 * extracted / max(scanned, 1):.1f}%) [{mode}]'
        ))
        if samples:
            self.stdout.write('Samples:')
            for s in samples:
                self.stdout.write(s)
        if extracted and not options['dry_run']:
            self.stdout.write(
                'Salary fields updated. HAS scores pick this up at the next '
                'daily rescore (or run: python manage.py score_listings --force)'
            )
