from django.db import migrations, models

INDEX_SQL = (
    'CREATE INDEX CONCURRENTLY IF NOT EXISTS "has_band_published_idx" '
    'ON "jobs_hiringactivityscore" ("score_band") WHERE "published_to_board"'
)


def create_index(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == 'postgresql':
        # CONCURRENTLY: no write lock on the score table (the sync/rescore writes
        # to it). Needs atomic = False. IF NOT EXISTS makes a retry safe.
        schema_editor.execute(INDEX_SQL)
    else:
        schema_editor.execute(
            'CREATE INDEX IF NOT EXISTS "has_band_published_idx" '
            'ON "jobs_hiringactivityscore" ("score_band") WHERE "published_to_board"'
        )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('jobs', '0029_scrapedjoblisting_is_us'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='hiringactivityscore',
                    index=models.Index(
                        condition=models.Q(('published_to_board', True)),
                        fields=['score_band'],
                        name='has_band_published_idx',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    create_index,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
