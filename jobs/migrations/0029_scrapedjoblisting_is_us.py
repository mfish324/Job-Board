from django.db import migrations, models

from jobs.us_location import (
    PG_ANYWHERE_CI, PG_ENDS_WITH_CS, PG_STATE_SPACE_CI,
)

BATCH = 10000


def backfill_is_us(apps, schema_editor):
    """Backfill in id-range batches (non-atomic migration => each batch commits)
    so we never hold one long transaction on the small production DB."""
    if schema_editor.connection.vendor != 'postgresql':
        # Dev/test (SQLite): fall back to the Python implementation.
        from jobs.us_location import is_us_location
        Model = apps.get_model('jobs', 'ScrapedJobListing')
        for pk, loc in Model.objects.values_list('pk', 'location').iterator():
            if is_us_location(loc):
                Model.objects.filter(pk=pk).update(is_us=True)
        return

    with schema_editor.connection.cursor() as cur:
        cur.execute('SELECT COALESCE(MIN(id), 0), COALESCE(MAX(id), 0) FROM jobs_scrapedjoblisting')
        lo, hi = cur.fetchone()
        start = lo
        while start <= hi:
            cur.execute(
                """
                UPDATE jobs_scrapedjoblisting
                SET is_us = TRUE
                WHERE id >= %s AND id < %s
                  AND (location ~* %s OR location ~ %s OR location ~* %s)
                """,
                [start, start + BATCH, PG_ANYWHERE_CI, PG_ENDS_WITH_CS, PG_STATE_SPACE_CI],
            )
            start += BATCH


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('jobs', '0028_sitevisit_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='scrapedjoblisting',
            name='is_us',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_is_us, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='scrapedjoblisting',
            index=models.Index(
                condition=models.Q(('is_us', True), ('published_to_board', True)),
                fields=['-date_last_seen', 'status'],
                name='sjl_us_published_idx',
            ),
        ),
    ]
