# Align FeaturedEmployer.industry with genzjobs CompanyATS.industryCategory
# (2026-05-13)

from django.db import migrations, models


# Old short-keys -> new genzjobs-aligned enum values.
# Only values currently used by the seed are mapped non-trivially; the rest
# fall to OTHER. pharma falls to HEALTHCARE.
FORWARD_MAP = {
    'tech': 'TECHNOLOGY',
    'finance': 'FINANCE_AND_BANKING',
    'healthcare': 'HEALTHCARE',
    'consulting': 'CONSULTING',
    'aerospace': 'AEROSPACE_AND_DEFENSE',
    'government': 'GOVERNMENT',
    'retail': 'RETAIL_AND_ECOMMERCE',
    'energy': 'OTHER',
    'pharma': 'HEALTHCARE',
    'other': 'OTHER',
}

REVERSE_MAP = {
    'TECHNOLOGY': 'tech',
    'FINANCE_AND_BANKING': 'finance',
    'HEALTHCARE': 'healthcare',
    'CONSULTING': 'consulting',
    'AEROSPACE_AND_DEFENSE': 'aerospace',
    'GOVERNMENT': 'government',
    'RETAIL_AND_ECOMMERCE': 'retail',
    'MEDIA_AND_ENTERTAINMENT': 'other',  # No legacy equivalent
    'OTHER': 'other',
}


def forward(apps, schema_editor):
    FeaturedEmployer = apps.get_model('directory', 'FeaturedEmployer')
    for emp in FeaturedEmployer.objects.all():
        new_val = FORWARD_MAP.get(emp.industry, 'OTHER')
        if new_val != emp.industry:
            emp.industry = new_val
            emp.save(update_fields=['industry'])


def reverse(apps, schema_editor):
    FeaturedEmployer = apps.get_model('directory', 'FeaturedEmployer')
    for emp in FeaturedEmployer.objects.all():
        old_val = REVERSE_MAP.get(emp.industry, 'other')
        if old_val != emp.industry:
            emp.industry = old_val
            emp.save(update_fields=['industry'])


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0002_add_link_health_fields"),
    ]

    operations = [
        # Bump max_length first so longer enum strings can be written.
        migrations.AlterField(
            model_name="featuredemployer",
            name="industry",
            field=models.CharField(
                choices=[
                    ('tech', 'Tech'),
                    ('finance', 'Finance/Banking'),
                    ('healthcare', 'Healthcare'),
                    ('aerospace', 'Aerospace/Defense'),
                    ('government', 'Government'),
                    ('consulting', 'Consulting'),
                    ('retail', 'Retail'),
                    ('energy', 'Energy'),
                    ('pharma', 'Pharma'),
                    ('other', 'Other'),
                ],
                default='other',
                max_length=30,
            ),
        ),
        migrations.RunPython(forward, reverse),
        # Now apply the new choice set + index + default.
        migrations.AlterField(
            model_name="featuredemployer",
            name="industry",
            field=models.CharField(
                choices=[
                    ('TECHNOLOGY', 'Technology'),
                    ('FINANCE_AND_BANKING', 'Finance & Banking'),
                    ('HEALTHCARE', 'Healthcare'),
                    ('CONSULTING', 'Consulting'),
                    ('AEROSPACE_AND_DEFENSE', 'Aerospace & Defense'),
                    ('GOVERNMENT', 'Government'),
                    ('RETAIL_AND_ECOMMERCE', 'Retail & E-Commerce'),
                    ('MEDIA_AND_ENTERTAINMENT', 'Media & Entertainment'),
                    ('OTHER', 'Other'),
                ],
                db_index=True,
                default='OTHER',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="directoryclick",
            name="industry",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
    ]
