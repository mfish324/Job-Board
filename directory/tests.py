from django.test import TestCase, RequestFactory
from django.urls import reverse

from .models import (
    FeaturedEmployer, JobTitleMapping, DirectoryEmployerCategory,
    EmployerTitleOverride, DirectoryClick,
)
from .utils import match_title, build_deep_link, get_directory_results


class TitleMatchingTests(TestCase):
    def setUp(self):
        self.devops = JobTitleMapping.objects.create(
            canonical_title='DevOps Engineer',
            slug='devops-engineer',
            search_aliases=[
                'devops', 'dev ops', 'site reliability', 'sre',
                'infrastructure engineer', 'platform engineer',
            ],
        )
        self.swe = JobTitleMapping.objects.create(
            canonical_title='Software Engineer',
            slug='software-engineer',
            search_aliases=[
                'software engineer', 'software developer', 'frontend',
                'backend', 'web developer',
            ],
        )

    def test_exact_match(self):
        mapping, alias = match_title('devops')
        self.assertEqual(mapping, self.devops)

    def test_longer_alias_preferred(self):
        mapping, alias = match_title('site reliability engineer')
        self.assertEqual(mapping, self.devops)
        self.assertEqual(alias, 'site reliability')

    def test_query_with_location_still_matches(self):
        mapping, alias = match_title('devops engineer san francisco')
        self.assertEqual(mapping, self.devops)

    def test_no_match(self):
        mapping, alias = match_title('underwater basket weaving')
        self.assertIsNone(mapping)

    def test_empty_query(self):
        mapping, alias = match_title('')
        self.assertIsNone(mapping)

    def test_case_insensitive(self):
        mapping, alias = match_title('DevOps Engineer')
        self.assertEqual(mapping, self.devops)

    def test_software_engineer_match(self):
        mapping, alias = match_title('software engineer')
        self.assertEqual(mapping, self.swe)


class DeepLinkTests(TestCase):
    def setUp(self):
        self.google = FeaturedEmployer.objects.create(
            name='Google',
            slug='google',
            career_url='https://careers.google.com/jobs/results/',
            url_pattern='{base_url}?q={query}&location={location}',
            supports_location=True,
        )
        self.devops = JobTitleMapping.objects.create(
            canonical_title='DevOps Engineer',
            slug='devops-engineer',
            search_aliases=['devops', 'sre', 'site reliability'],
        )

    def test_basic_deep_link(self):
        url = build_deep_link(self.google, 'software engineer', 'New York')
        self.assertIn('q=software+engineer', url)
        self.assertIn('location=New+York', url)
        self.assertTrue(url.startswith('https://careers.google.com'))

    def test_deep_link_with_override(self):
        EmployerTitleOverride.objects.create(
            employer=self.google,
            canonical_title=self.devops,
            preferred_search_term='site reliability engineer',
        )
        url = build_deep_link(self.google, 'devops', '', self.devops)
        self.assertIn('site+reliability+engineer', url)

    def test_deep_link_with_category_search_term(self):
        DirectoryEmployerCategory.objects.create(
            employer=self.google,
            canonical_category='DevOps Engineer',
            employer_search_term='cloud operations engineer',
            is_active=True,
        )
        # No override, should fall back to category search term
        url = build_deep_link(self.google, 'devops', '', self.devops)
        self.assertIn('cloud+operations+engineer', url)

    def test_deep_link_empty_location(self):
        url = build_deep_link(self.google, 'engineer', '')
        self.assertIn('q=engineer', url)
        self.assertIn('location=', url)

    def test_deep_link_special_characters(self):
        url = build_deep_link(self.google, 'C++ developer', '')
        self.assertIn('C%2B%2B', url)


class SearchIntegrationTests(TestCase):
    def setUp(self):
        self.fa_mapping = JobTitleMapping.objects.create(
            canonical_title='Financial Analyst',
            slug='financial-analyst',
            search_aliases=['financial analyst', 'finance analyst'],
        )
        self.gs = FeaturedEmployer.objects.create(
            name='Goldman Sachs',
            slug='goldman-sachs',
            career_url='https://higher.gs.com/results',
            url_pattern='{base_url}?q={query}',
            is_active=True,
            display_priority=10,
        )
        self.jpm = FeaturedEmployer.objects.create(
            name='JPMorgan Chase',
            slug='jpmorgan-chase',
            career_url='https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions',
            url_pattern='{base_url}?keyword={query}',
            is_active=True,
            display_priority=10,
        )
        DirectoryEmployerCategory.objects.create(
            employer=self.gs, canonical_category='Financial Analyst',
            estimated_count=87, is_active=True,
        )
        DirectoryEmployerCategory.objects.create(
            employer=self.jpm, canonical_category='Financial Analyst',
            estimated_count=200, is_active=True,
        )

    def test_search_returns_directory_results(self):
        results, mapping = get_directory_results('financial analyst')
        self.assertEqual(mapping, self.fa_mapping)
        self.assertEqual(len(results), 2)
        employer_names = [r['employer'].name for r in results]
        self.assertIn('Goldman Sachs', employer_names)
        self.assertIn('JPMorgan Chase', employer_names)

    def test_no_match_returns_empty(self):
        results, mapping = get_directory_results('underwater basket weaving')
        self.assertEqual(results, [])
        self.assertIsNone(mapping)

    def test_inactive_employer_excluded(self):
        self.gs.is_active = False
        self.gs.save()
        results, _ = get_directory_results('financial analyst')
        employer_names = [r['employer'].name for r in results]
        self.assertNotIn('Goldman Sachs', employer_names)


class ClickTrackingTests(TestCase):
    def setUp(self):
        self.employer = FeaturedEmployer.objects.create(
            name='Test Corp',
            slug='test-corp',
            career_url='https://careers.testcorp.com/',
            url_pattern='{base_url}?q={query}',
            is_active=True,
        )

    def test_redirect_logs_click_and_returns_302(self):
        url = reverse('directory:employer_redirect', kwargs={'slug': 'test-corp'})
        response = self.client.get(url, {'q': 'engineer', 'source': 'search_results'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('careers.testcorp.com', response.url)

        click = DirectoryClick.objects.first()
        self.assertIsNotNone(click)
        self.assertEqual(click.employer, self.employer)
        self.assertEqual(click.search_query, 'engineer')
        self.assertEqual(click.source, 'search_results')


class SeedIdempotencyTests(TestCase):
    def test_seed_twice_no_duplicates(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('seed_directory', stdout=out)
        first_count = FeaturedEmployer.objects.count()

        out = StringIO()
        call_command('seed_directory', stdout=out)
        second_count = FeaturedEmployer.objects.count()

        self.assertEqual(first_count, second_count)
        self.assertGreater(first_count, 0)

    def test_seed_creates_title_mappings(self):
        from django.core.management import call_command
        from io import StringIO

        call_command('seed_directory', stdout=StringIO())
        self.assertTrue(JobTitleMapping.objects.filter(
            canonical_title='Software Engineer'
        ).exists())
        self.assertTrue(JobTitleMapping.objects.filter(
            canonical_title='DevOps Engineer'
        ).exists())
