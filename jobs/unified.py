"""
UnifiedListing wrapper for merging Job and ScrapedJobListing into a single feed.

Normalizes both models into a common interface for templates.
"""
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta


class UnifiedListing:
    """
    Lightweight wrapper that normalizes Job and ScrapedJobListing
    into a common interface for the unified /jobs/ feed.
    """

    def __init__(self, obj):
        self._obj = obj
        self._is_verified = hasattr(obj, 'posted_by')

    def __getattr__(self, name):
        """Pass through attribute access to the underlying model."""
        return getattr(self._obj, name)

    @property
    def id(self):
        return self._obj.id

    @property
    def title(self):
        return self._obj.title

    @property
    def company_name(self):
        if self._is_verified:
            return self._obj.company
        return self._obj.company_name

    @property
    def description(self):
        return self._obj.description

    @property
    def location(self):
        return self._obj.location or ''

    @property
    def salary_display(self):
        if self._is_verified:
            return self._obj.salary or ''
        # ScrapedJobListing has salary_min/salary_max
        s_min = self._obj.salary_min
        s_max = self._obj.salary_max
        if not s_min and not s_max:
            return ''
        currency = getattr(self._obj, 'salary_currency', 'USD')

        def fmt(n):
            if n >= 1000:
                return f'{n / 1000:.0f}K'
            return str(int(n))

        if s_min and s_max:
            return f'${fmt(s_min)} - ${fmt(s_max)} {currency}'
        elif s_min:
            return f'From ${fmt(s_min)} {currency}'
        return f'Up to ${fmt(s_max)} {currency}'

    @property
    def has_salary(self):
        if self._is_verified:
            return bool(self._obj.salary)
        return bool(self._obj.salary_min or self._obj.salary_max)

    @property
    def posted_date(self):
        if self._is_verified:
            return self._obj.posted_date
        return self._obj.date_posted_external or self._obj.date_first_seen

    @property
    def job_type_display(self):
        if self._is_verified:
            return self._obj.get_job_type_display()
        jt = self._obj.job_type
        return jt.replace('_', ' ').title() if jt else ''

    @property
    def experience_level_display(self):
        if self._is_verified:
            return self._obj.get_experience_level_display()
        el = self._obj.experience_level
        return el.replace('_', ' ').title() if el else ''

    @property
    def remote_status_display(self):
        if self._is_verified:
            return self._obj.get_remote_status_display()
        rs = self._obj.remote_status
        return rs.replace('_', ' ').title() if rs else ''

    @property
    def detail_url(self):
        if self._is_verified:
            return reverse('job_detail', args=[self._obj.id])
        return reverse('observed_listing_detail', args=[self._obj.id])

    @property
    def is_verified(self):
        return self._is_verified

    @property
    def is_observed(self):
        return not self._is_verified

    @property
    def has_score_value(self):
        """Return the HAS total_score or None."""
        if self._is_verified:
            return None
        try:
            return self._obj.activity_score.total_score
        except Exception:
            return None

    def compute_sort_score(self, sort_mode):
        now = timezone.now()
        age_days = (now - self.posted_date).total_seconds() / 86400

        # Verified postings always sort above observed in all modes.
        # We add 100000 to ensure verified never interleaves with observed.
        verified_boost = 100000 if self._is_verified else 0

        if sort_mode == 'newest':
            # Chronological within each group
            return verified_boost + self.posted_date.timestamp() / 1e10

        elif sort_mode == 'activity':
            # HAS score descending; verified treated as score=100
            if self._is_verified:
                return verified_boost + (100 - min(age_days, 100))
            has = self.has_score_value or 0
            return has

        else:
            # "relevant" (default): blended score
            freshness = max(0, 30 - age_days)  # 0-30 pts

            if self._is_verified:
                return verified_boost + freshness
            else:
                has = self.has_score_value or 0
                return (has * 0.5) + freshness

    @staticmethod
    def merge_querysets(verified_qs, observed_qs, sort_mode='relevant'):
        """
        Wrap both querysets in UnifiedListing, merge, sort, and return a list.
        """
        items = []
        for job in verified_qs:
            items.append(UnifiedListing(job))
        for listing in observed_qs:
            items.append(UnifiedListing(listing))

        reverse_sort = True  # Higher score = first
        items.sort(key=lambda x: x.compute_sort_score(sort_mode), reverse=reverse_sort)

        return items
