"""
Bulk-tag FeaturedEmployer rows with an industry category from a text file.

Usage:
    python manage.py tag_employer_industry --file path/to/industries.txt
    python manage.py tag_employer_industry --file path/to/industries.txt --dry-run

Input file format: one entry per line as `Name|Industry`. Lines beginning
with `#` and blank lines are ignored.

The Industry side accepts either:
  - enum values: TECHNOLOGY, FINANCE_AND_BANKING, HEALTHCARE, CONSULTING,
    AEROSPACE_AND_DEFENSE, GOVERNMENT, RETAIL_AND_ECOMMERCE,
    MEDIA_AND_ENTERTAINMENT, OTHER
  - friendly names: "Technology", "Finance & Banking", "Healthcare",
    "Consulting", "Aerospace & Defense", "Government",
    "Retail & E-Commerce", "Media & Entertainment", "Other"

Name matching is case-insensitive against FeaturedEmployer.name. The
operation is idempotent. Names that don't match any directory row are
written to scripts/missing-directory-industries.txt for manual triage —
no stub rows are created.
"""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from directory.models import FeaturedEmployer


# Build a forgiving label -> enum-value map covering both enum and friendly forms.
INDUSTRY_LOOKUP = {}
for enum_value, friendly in FeaturedEmployer.INDUSTRY_CHOICES:
    INDUSTRY_LOOKUP[enum_value.lower()] = enum_value
    INDUSTRY_LOOKUP[friendly.lower()] = enum_value
    # Also accept variants without separators (e.g. "financebanking" or "fb")
    stripped = friendly.lower().replace('&', 'and').replace('-', ' ')
    stripped = ' '.join(stripped.split())  # collapse whitespace
    INDUSTRY_LOOKUP[stripped] = enum_value


def normalize_industry(raw):
    """Return the canonical enum value for a user-supplied industry string."""
    if not raw:
        return None
    return INDUSTRY_LOOKUP.get(raw.strip().lower())


class Command(BaseCommand):
    help = 'Bulk-tag FeaturedEmployer rows with an industry category from a file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', required=True,
            help='Path to text file with Name|Industry entries (one per line).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Preview changes without saving.',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']

        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')

        # Parse the file
        entries = []  # list of (line_number, name, industry_str)
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if '|' not in line:
                    self.stderr.write(self.style.WARNING(
                        f'Line {line_no}: missing "|" separator — skipped: {line!r}'
                    ))
                    continue
                name, industry_str = [s.strip() for s in line.split('|', 1)]
                if not name or not industry_str:
                    self.stderr.write(self.style.WARNING(
                        f'Line {line_no}: empty name or industry — skipped'
                    ))
                    continue
                entries.append((line_no, name, industry_str))

        if not entries:
            self.stdout.write(self.style.WARNING('No usable entries found.'))
            return

        self.stdout.write(f'Processing {len(entries)} entries from {file_path}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved.'))

        updated = 0
        unchanged = 0
        bad_industry = []
        missing = []

        for line_no, name, industry_str in entries:
            industry = normalize_industry(industry_str)
            if industry is None:
                bad_industry.append((line_no, name, industry_str))
                continue

            try:
                emp = FeaturedEmployer.objects.get(name__iexact=name)
            except FeaturedEmployer.DoesNotExist:
                missing.append(name)
                continue
            except FeaturedEmployer.MultipleObjectsReturned:
                # Pick first; report.
                self.stderr.write(self.style.WARNING(
                    f'Line {line_no}: multiple matches for {name!r}; using first'
                ))
                emp = FeaturedEmployer.objects.filter(name__iexact=name).first()

            if emp.industry == industry:
                unchanged += 1
                self.stdout.write(f'  = {emp.name} (already {industry})')
                continue

            self.stdout.write(f'  + {emp.name}: {emp.industry} -> {industry}')
            if not dry_run:
                emp.industry = industry
                emp.save(update_fields=['industry'])
            updated += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Updated: {updated}  Unchanged: {unchanged}  '
            f'Missing: {len(missing)}  Bad industry: {len(bad_industry)}'
        ))

        if bad_industry:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Unrecognized industry values:'))
            for line_no, name, industry_str in bad_industry:
                self.stdout.write(f'  Line {line_no}: {name} | {industry_str!r}')

        if missing:
            scripts_dir = Path(file_path).resolve().parent
            out_path = scripts_dir / 'missing-directory-industries.txt'
            header = (
                f"# Names from {Path(file_path).name} not found in FeaturedEmployer.\n"
                "# To onboard:\n"
                "#   1. Add the employer via Django admin (/admin/directory/featuredemployer/)\n"
                "#      or by editing directory/management/commands/seed_directory.py + running\n"
                "#      `python manage.py seed_directory`\n"
                "#   2. Re-run: python manage.py tag_employer_industry --file <same file>\n"
                "#\n"
            )
            if not dry_run:
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(header)
                    for name in missing:
                        f.write(f'{name}\n')
                self.stdout.write('')
                self.stdout.write(self.style.WARNING(
                    f'{len(missing)} unmatched name(s) written to {out_path}'
                ))
            else:
                self.stdout.write('')
                self.stdout.write(self.style.WARNING(
                    f'{len(missing)} unmatched name(s) would be written to {out_path}'
                ))
            for name in missing:
                self.stdout.write(f'  - {name}')
