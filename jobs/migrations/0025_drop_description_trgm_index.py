"""
Drop the GIN trigram index on jobs_scrapedjoblisting.description.

The first version of 0024 created jobs_sjl_description_trgm, and on the live DB
that migration completed before it was revised — so the 138 MB description index
exists and 0024 is recorded as applied (the revised 0024 is skipped there). This
migration removes it on existing databases.

Why drop it (measured on prod with EXPLAIN ANALYZE):
- A 4-column ILIKE search ('%data scientist%') using the description trigram index
  was 6.16s: the description bitmap matched 7,983 candidate rows (common trigrams),
  forcing a Bitmap Heap Scan that rechecked ILIKE on ~8k large-text tuples.
- The same search over just title/company_name/location (their trigram indexes
  return tiny candidate sets) is 90ms.
So the description index is both heavy (138 MB + per-sync GIN maintenance) AND
slower for search. The live search Q only uses title/company_name/location.

Notes:
- atomic = False + DROP INDEX CONCURRENTLY: avoids locking the live table.
- Guarded on connection.vendor: no-op on SQLite dev/test.
- No reverse recreate (we never want this index back); reverse is a no-op.
"""

from django.db import migrations


DESCRIPTION_INDEX = "jobs_sjl_description_trgm"


def drop_description_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {DESCRIPTION_INDEX}")


def noop(apps, schema_editor):
    # Intentionally do not recreate the description index on reverse.
    return


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("jobs", "0024_scrapedlisting_trigram_search_indexes"),
    ]

    operations = [
        migrations.RunPython(drop_description_index, noop),
    ]
