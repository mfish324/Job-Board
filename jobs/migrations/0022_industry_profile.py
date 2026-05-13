# Generated for industry weight profile system (2026-05-13)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0021_add_description_summary"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapedjoblisting",
            name="industry_category",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Industry enum from genzjobs CompanyATS.industryCategory (e.g. TECHNOLOGY)",
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="hiringactivityscore",
            name="weight_profile",
            field=models.CharField(default="default", max_length=50),
        ),
        migrations.AddField(
            model_name="hiringactivityscore",
            name="weight_profile_version",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
