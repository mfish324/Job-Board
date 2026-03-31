from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Job, ScrapedJobListing


class StaticViewSitemap(Sitemap):
    changefreq = 'weekly'

    _priorities = {
        'home': 1.0,
        'job_list': 0.9,
    }

    def items(self):
        return [
            'home', 'job_list', 'about', 'has_info',
            'employer_guide', 'privacy_policy', 'terms_of_service', 'contact',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self._priorities.get(item, 0.6)


class VerifiedJobSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return Job.objects.filter(is_active=True).order_by('-posted_date')

    def lastmod(self, obj):
        return obj.last_refreshed or obj.posted_date

    def location(self, obj):
        return obj.get_absolute_url()


class ObservedJobSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.7

    def items(self):
        return (
            ScrapedJobListing.objects
            .filter(published_to_board=True)
            .filter(activity_score__total_score__gte=65)
            .order_by('-date_last_seen')
        )

    def lastmod(self, obj):
        return obj.date_last_seen or obj.date_first_seen

    def location(self, obj):
        return obj.get_absolute_url()
