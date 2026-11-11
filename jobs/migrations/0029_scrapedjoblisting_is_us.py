from django.db import migrations, models

from jobs.us_location import (
    PG_ANYWHERE_CI, PG_ENDS_WITH_CS, PG_STATE_SPACE_CI,
)

BATCH = 5000


def add_column_if_missing(apps, schema_editor):
    """Idempotent AddField. The migration is non-atomic, so a cancelled/failed
    run can leave the column behind; a plain AddField would then fail on retry.
    On Postgres a short lock_timeout makes us fail fast instead of queueing
    behind long-running queries (a queued ACCESS EXCLUSIVE lock blocks every
    new query on the table behind it)."""
    conn = schema_editor.connection
    Model = apps.get_model('jobs', 'ScrapedJobListing')
    table = Model._meta.db_table
    with conn.cursor() as cur:
        existing = {c.name for c in conn.introspection.get_table_description(cur, table)}
    if 'is_us' in existing:
        return
    field = models.BooleanField(default=False)
    field.set_attributes_from_name('is_us')
    if conn.vendor == 'postgresql':
        schema_editor.execute("SET lock_timeout = '20s'")
    try:
        schema_editor.add_field(Model, field)
    finally:
        if conn.vendor == 'postgresql':
            schema_editor.execute('RESET lock_timeout')


def backfill_is_us(apps, schema_editor):
    """Backfill only PUBLISHED rows (the only rows the /jobs/ filter reads, ~36k
    of ~155k) in small id-range batches that each commit. Every UPDATE rewrites
    the row and touches all its indexes (incl. trigram GINs) on a 0.1-CPU DB, so
    skipping unpublished rows is a ~4x saving. Other rows get is_us on their
    next save() (the sync saves every listing). Idempotent: skips rows already
    set, so a retry resumes where it left off."""
    conn = schema_editor.connection
    if conn.vendor != 'postgresql':
        from jobs.us_location import is_us_location
        Model = apps.get_model('jobs', 'ScrapedJobListing')
        for pk, loc in Model.objects.values_list('pk', 'location').iterator():
            if is_us_location(loc):
                Model.objects.filter(pk=pk).update(is_us=True)
        return

    with conn.cursor() as cur:
        cur.execute('SELECT COALESCE(MIN(id), 0), COALESCE(MAX(id), 0) FROM jobs_scrapedjoblisting')
        lo, hi = cur.fetchone()
        start = lo
        while start <= hi:
            cur.execute(
                """
                UPDATE jobs_scrapedjoblisting
                SET is_us = TRUE
                WHERE id >= %s AND id < %s
                  AND published_to_board AND NOT is_us
                  AND (location ~* %s OR location ~ %s OR location ~* %s)
                """,
                [start, start + BATCH, PG_ANYWHERE_CI, PG_ENDS_WITH_CS, PG_STATE_SPACE_CI],
            )
            start += BATCH


INDEX_SQL = (
    'CREATE INDEX IF NOT EXISTS "sjl_us_published_idx" ON "jobs_scrapedjoblisting" '
    '("date_last_seen" DESC, "status") WHERE ("is_us" AND "published_to_board")'
)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('jobs', '0028_sitevisit_indexes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='scrapedjoblisting',
                    name='is_us',
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_column_if_missing, migrations.RunPython.noop),
            ],
        ),
        migrations.RunPython(backfill_is_us, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='scrapedjoblisting',
                    index=models.Index(
                        condition=models.Q(('is_us', True), ('published_to_board', True)),
                        fields=['-date_last_seen', 'status'],
                        name='sjl_us_published_idx',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(INDEX_SQL, 'DROP INDEX IF EXISTS "sjl_us_published_idx"'),
            ],
        ),
    ]
