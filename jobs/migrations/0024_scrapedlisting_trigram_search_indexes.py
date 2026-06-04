"""
Add pg_trgm GIN indexes so substring search (`col ILIKE '%term%'`) on the
observed listings table is index-backed instead of a sequential scan.

Background: /jobs/?search= ran `title/company_name/location/description ILIKE
'%term%'` over the ~67k-row jobs_scrapedjoblisting with no trigram index. Measured
on prod, the description ILIKE alone took ~17s of a ~21s query and tripped the
60s gunicorn timeout under load (commit f1e4e86 dropped description from the
search as an immediate fix). These GIN trigram indexes let Postgres satisfy the
ILIKEs from an index (BitmapOr across the four columns), making the full
four-column search ~milliseconds — which lets us safely restore description
search.

Notes:
- atomic = False: CREATE/DROP INDEX CONCURRENTLY cannot run inside a transaction.
- CONCURRENTLY: build.sh runs `migrate` during deploy while the OLD code is still
  serving traffic; a plain CREATE INDEX would take an ACCESS EXCLUSIVE lock on the
  live table for the (multi-minute) build. CONCURRENTLY avoids the lock.
- Guarded on connection.vendor: local dev / tests run on SQLite, which has neither
  pg_trgm nor GIN. There it's a no-op (ILIKE still works unindexed on the tiny dev
  DB), so this migration is portable.
- Pure performance indexes, not declared in model Meta — managed here via RunPython
  with an explicit reverse, so makemigrations won't try to re-manage them.
- Requires permission to CREATE EXTENSION pg_trgm (a "trusted" extension on PG13+;
  Neon/Render app roles can normally create it). If that fails, enable pg_trgm once
  via the DB dashboard, then re-run migrate.
"""

from django.db import migrations


# (index_name, column) pairs on jobs_scrapedjoblisting.
TRGM_INDEXES = [
    ("jobs_sjl_title_trgm", "title"),
    ("jobs_sjl_company_name_trgm", "company_name"),
    ("jobs_sjl_location_trgm", "location"),
    ("jobs_sjl_description_trgm", "description"),
]


def create_trgm_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
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
