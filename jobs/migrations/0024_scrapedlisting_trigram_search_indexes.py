"""
Add pg_trgm GIN indexes so substring search (`col ILIKE '%term%'`) on the
observed listings table is index-backed instead of a sequential scan.

Indexes title, company_name, and location only. We deliberately do NOT index the
`description` column: a GIN trigram index on full job-description text proved
disproportionately expensive — it grew past 120 MB and took 20+ min to build,
loading the DB, and would add real write overhead to every daily sync_genzjobs.
The /jobs/ search query only filters title/company_name/location (description was
dropped from the search in commit f1e4e86 to stop the 60s timeouts), so those
three small indexes (a few MB each) make the live search ~milliseconds, which is
the whole win. Description text search is not restored.

A first version of this migration also created jobs_sjl_description_trgm; if an
interrupted CREATE INDEX CONCURRENTLY left that index behind (INVALID), the
forward step drops it so it can't linger consuming disk.

Notes:
- atomic = False: CREATE/DROP INDEX CONCURRENTLY cannot run inside a transaction.
- CONCURRENTLY: build.sh runs `migrate` during deploy while the OLD code still
  serves traffic; a plain CREATE INDEX would take an ACCESS EXCLUSIVE lock on the
  live table for the build. CONCURRENTLY avoids the lock.
- Guarded on connection.vendor: local dev / tests run on SQLite (no pg_trgm/GIN),
  where this is a no-op. Verified applies clean on SQLite.
- Pure performance indexes, not declared in model Meta — managed here via RunPython
  with an explicit reverse.
- Requires permission to CREATE EXTENSION pg_trgm (a "trusted" extension on PG13+).
"""

from django.db import migrations


# (index_name, column) pairs on jobs_scrapedjoblisting. Small columns only.
TRGM_INDEXES = [
    ("jobs_sjl_title_trgm", "title"),
    ("jobs_sjl_company_name_trgm", "company_name"),
    ("jobs_sjl_location_trgm", "location"),
]

# A prior version of this migration created this index on the large description
# column; drop it (it may exist INVALID from an interrupted concurrent build).
ORPHANED_INDEX = "jobs_sjl_description_trgm"


def create_trgm_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # Remove the heavy/abandoned description index if a previous attempt left it.
    schema_editor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {ORPHANED_INDEX}")
    for index_name, column in TRGM_INDEXES:
        schema_editor.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
            f"ON jobs_scrapedjoblisting USING gin ({column} gin_trgm_ops)"
        )


def drop_trgm_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for index_name, _column in TRGM_INDEXES:
        schema_editor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("jobs", "0023_socialcontentdraft_dailyghostreport_and_more"),
    ]

    operations = [
        migrations.RunPython(create_trgm_indexes, drop_trgm_indexes),
    ]
