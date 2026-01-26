from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job


class Command(BaseCommand):
    help = 'Deactivate jobs that have passed their expiration date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deactivated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        # Find all active jobs that have expired
        expired_jobs = Job.objects.filter(
            is_active=True,
            expires_at__lt=now
        )

        count = expired_jobs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No expired jobs found.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Would deactivate {count} job(s):'))
            for job in expired_jobs:
                self.stdout.write(f'  - {job.title} at {job.company} (expired: {job.expires_at})')
        else:
            # Deactivate expired jobs
            expired_jobs.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'Successfully deactivated {count} expired job(s).'))

            # Log the jobs that were deactivated
            for job in Job.objects.filter(
                is_active=False,
                expires_at__lt=now
            ).order_by('-expires_at')[:count]:
                self.stdout.write(f'  - {job.title} at {job.company}')
