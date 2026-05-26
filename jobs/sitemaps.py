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
    protocol = 'https'
    # Paginate so each sitemap page is a bounded, cheap query rather than
    # loading every row into one response (avoids worker memory spikes / timeouts).
    limit = 2000

    def items(self):
        # get_absolute_url + lastmod only need the pk and these date fields;
        # .only() avoids hauling every column for every row.
        return (
            Job.objects
            .filter(is_active=True)
            .only('pk', 'last_refreshed', 'posted_date')
            .order_by('-posted_date')
        )

    def lastmod(self, obj):
        return obj.last_refreshed or obj.posted_date

    def location(self, obj):
        return obj.get_absolute_url()


class ObservedJobSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.7
    protocol = 'https'
    limit = 2000

    def items(self):
        # .only() is critical here: ScrapedJobListing rows carry large
        # description / description_summary text we don't need for a sitemap.
        return (
            ScrapedJobListing.objects
            .filter(published_to_board=True)
            .filter(activity_score__total_score__gte=65)
            .only('pk', 'date_last_seen', 'date_first_seen')
            .order_by('-date_last_seen')
        )

    def lastmod(self, obj):
        return obj.date_last_seen or obj.date_first_seen

    def location(self, obj):
        return obj.get_absolute_url()
