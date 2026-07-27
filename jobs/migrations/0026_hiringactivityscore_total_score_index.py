"""
Add a btree index on jobs_hiringactivityscore.total_score.

The homepage (`home` view) queries the top 6 published observed listings
ordered by `-activity_score__total_score, -date_first_seen`. With no index
on total_score, Postgres has to pull all ~21-22k published/active listings,
do a per-row index lookup into jobs_hiringactivityscore (one Index Scan per
row via the listing_id index), and sort the joined set just to take 6 —
measured on prod with EXPLAIN ANALYZE at ~12.3s baseline (Index Searches:
21798, Buffers: read=27437). Under the 09:00 daily rescore's heavy UPDATE
load on this same table, that regularly pushed past the 60s gunicorn
timeout, producing near-daily "WORKER TIMEOUT" 500s on `GET /` clustered
around the 08:00-09:45 UTC cron windows (a different query than the one
fixed in c379083, which only cheapened the distinct-company-count queries
in the same view).

With total_score indexed, Postgres can scan jobs_hiringactivityscore in
score order and join outward to jobs_scrapedjoblisting, stopping as soon as
6 rows satisfy the published_to_board/status filter — high-scoring rows are
disproportionately likely to already be published (publish_threshold is a
function of total_score), so this should resolve to a small number of
probes instead of a full 21k-row scan+sort.

Notes:
- atomic = False + CREATE INDEX CONCURRENTLY: avoids locking the live table
  during deploy (same reasoning as 0024/0025).
- Guarded on connection.vendor: no-op on SQLite dev/test.
- Not declared in model Meta (consistent with the trigram indexes in 0024) —
  pure performance index managed here via RunPython.
"""

from django.db import migrations


INDEX_NAME = "jobs_has_total_score_idx"


def create_total_score_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
        f"ON jobs_hiringactivityscore (total_score)"
    )


def drop_total_score_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("jobs", "0025_drop_description_trgm_index"),
    ]

    operations = [
        migrations.RunPython(create_total_score_index, drop_total_score_index),
    ]
