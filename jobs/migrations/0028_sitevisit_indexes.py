from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0027_backfill_missing_userprofiles'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='sitevisit',
            index=models.Index(fields=['ip_address', 'visited_at'], name='sitevisit_ip_visited_idx'),
        ),
        migrations.AddIndex(
            model_name='sitevisit',
            index=models.Index(fields=['visited_at'], name='sitevisit_visited_idx'),
        ),
    ]
