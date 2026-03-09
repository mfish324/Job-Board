from django.db import models
from django.conf import settings
from django.utils.text import slugify


class FeaturedEmployer(models.Model):
    INDUSTRY_CHOICES = [
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
    ]

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    logo = models.ImageField(upload_to='directory/logos/', blank=True, null=True)
    description = models.CharField(max_length=300, blank=True,
                                   help_text='One-liner for card display')
    headquarters = models.CharField(max_length=200, blank=True)
    employee_count = models.CharField(max_length=50, blank=True,
                                      help_text='e.g. "180,000+ employees"')
    industry = models.CharField(max_length=20, choices=INDUSTRY_CHOICES, default='other')

    career_url = models.URLField(max_length=500,
                                 help_text='Career portal base URL')
    url_pattern = models.CharField(
        max_length=500,
        help_text='URL template: {base_url}?q={query}&location={location}'
    )
    supports_location = models.BooleanField(default=False,
                                            help_text='Does the career URL support a location parameter?')

    is_active = models.BooleanField(default=True)
    display_priority = models.IntegerField(default=100,
                                           help_text='Lower = higher priority in results')
    estimated_open_roles = models.PositiveIntegerField(default=0, blank=True)
    last_count_update = models.DateTimeField(null=True, blank=True)

    # Optional link to a verified employer account on RJRP
    verified_employer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='featured_employer_profile',
        help_text='Link to verified employer account if they have claimed this page'
    )

    date_added = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_priority', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def logo_initial(self):
        """First letter of company name for placeholder display."""
        return self.name[0].upper() if self.name else '?'

    @property
    def career_domain(self):
        """Extract domain from career URL for display."""
        from urllib.parse import urlparse
        try:
            return urlparse(self.career_url).netloc
        except Exception:
            return self.career_url


class JobTitleMapping(models.Model):
    canonical_title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    search_aliases = models.JSONField(
        default=list,
        help_text='List of search terms that map to this canonical title'
    )
    related_titles = models.ManyToManyField(
        'self', blank=True, symmetrical=True,
        help_text='Related canonical titles for "you might also like"'
    )

    class Meta:
        ordering = ['canonical_title']
        verbose_name_plural = 'Job title mappings'

    def __str__(self):
        return self.canonical_title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.canonical_title)
        super().save(*args, **kwargs)

    @property
    def alias_count(self):
        return len(self.search_aliases) if self.search_aliases else 0


class DirectoryEmployerCategory(models.Model):
    employer = models.ForeignKey(
        FeaturedEmployer, on_delete=models.CASCADE,
        related_name='categories'
    )
    canonical_category = models.CharField(max_length=200)
    employer_search_term = models.CharField(
        max_length=200, blank=True,
        help_text='What to pass as query on this employer\'s career site'
    )
    estimated_count = models.PositiveIntegerField(null=True, blank=True)
    last_count_update = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('employer', 'canonical_category')
        ordering = ['-estimated_count']
        verbose_name_plural = 'Directory employer categories'

    def __str__(self):
        return f'{self.employer.name} — {self.canonical_category}'


class EmployerTitleOverride(models.Model):
    employer = models.ForeignKey(
        FeaturedEmployer, on_delete=models.CASCADE,
        related_name='title_overrides'
    )
    canonical_title = models.ForeignKey(
        JobTitleMapping, on_delete=models.CASCADE,
        related_name='employer_overrides'
    )
    preferred_search_term = models.CharField(
        max_length=200,
        help_text="Employer's preferred search term for this role"
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('employer', 'canonical_title')

    def __str__(self):
        return f'{self.employer.name}: {self.canonical_title} -> "{self.preferred_search_term}"'


class DirectoryClick(models.Model):
    SOURCE_CHOICES = [
        ('search_results', 'Search Results'),
        ('directory_page', 'Directory Page'),
        ('employer_detail', 'Employer Detail'),
    ]

    employer = models.ForeignKey(
        FeaturedEmployer, on_delete=models.CASCADE,
        related_name='clicks'
    )
    search_query = models.CharField(max_length=300, blank=True)
    location = models.CharField(max_length=200, blank=True)
    category = models.ForeignKey(
        JobTitleMapping, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    session_key = models.CharField(max_length=40, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.employer.name} click — {self.timestamp:%Y-%m-%d %H:%M}'
