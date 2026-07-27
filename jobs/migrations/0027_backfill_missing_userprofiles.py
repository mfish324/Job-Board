"""
Backfill UserProfile for any existing User missing one.

UserProfile is only ever created explicitly inside the job seeker/employer/
recruiter signup forms (forms.py). Accounts created outside that path —
Google OAuth signups (django-allauth, SOCIALACCOUNT_AUTO_SIGNUP=True) or
Django superusers — never got a UserProfile, so they 500 on any page that
assumes one exists (e.g. edit_profile: `request.user.userprofile` with no
hasattr guard). Found on prod 2026-07-27: 4 of 32 accounts affected,
including at least one real signed-up user, not just superusers/placeholders.

This is a one-time backfill; jobs/signals.py now hooks allauth's
user_signed_up signal so future OAuth signups get a profile automatically.
Defaults user_type to 'job_seeker' — the same default the signal uses, and
the least-privileged type (doesn't grant employer/recruiter capabilities to
an account that never asked for them).
"""

from django.db import migrations


def backfill_missing_profiles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('jobs', 'UserProfile')
    for user in User.objects.filter(userprofile__isnull=True):
        UserProfile.objects.create(user=user, user_type='job_seeker')


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0026_hiringactivityscore_total_score_index"),
    ]

    operations = [
        migrations.RunPython(backfill_missing_profiles, noop),
    ]
