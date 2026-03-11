from django.core.management.base import BaseCommand
from django.utils import timezone
from directory.models import (
    FeaturedEmployer, JobTitleMapping, DirectoryEmployerCategory,
    EmployerTitleOverride,
)


EMPLOYERS = [
    # Tech
    {
        'name': 'Google',
        'industry': 'tech',
        'headquarters': 'Mountain View, CA',
        'employee_count': '180,000+ employees',
        'description': 'Global technology leader in search, cloud computing, and AI.',
        'career_url': 'https://careers.google.com/jobs/results/',
        'url_pattern': '{base_url}?q={query}&location={location}',
        'supports_location': True,
        'display_priority': 10,
        'estimated_open_roles': 2500,
    },
    {
        'name': 'Apple',
        'industry': 'tech',
        'headquarters': 'Cupertino, CA',
        'employee_count': '160,000+ employees',
        'description': 'Consumer electronics, software, and services company.',
        'career_url': 'https://jobs.apple.com/en-us/search',
        'url_pattern': '{base_url}?search={query}&location={location}',
        'supports_location': True,
        'display_priority': 10,
        'estimated_open_roles': 3000,
    },
    {
        'name': 'Amazon',
        'industry': 'tech',
        'headquarters': 'Seattle, WA',
        'employee_count': '1,500,000+ employees',
        'description': 'E-commerce, cloud computing (AWS), and technology conglomerate.',
        'career_url': 'https://www.amazon.jobs/en/search',
        'url_pattern': '{base_url}?base_query={query}&loc_query={location}',
        'supports_location': True,
        'display_priority': 10,
        'estimated_open_roles': 12000,
    },
    {
        'name': 'Microsoft',
        'industry': 'tech',
        'headquarters': 'Redmond, WA',
        'employee_count': '220,000+ employees',
        'description': 'Software, cloud services (Azure), and enterprise solutions.',
        'career_url': 'https://careers.microsoft.com/us/en/search-results',
        'url_pattern': '{base_url}?keywords={query}&location={location}',
        'supports_location': True,
        'display_priority': 10,
        'estimated_open_roles': 8000,
    },
    {
        'name': 'Meta',
        'industry': 'tech',
        'headquarters': 'Menlo Park, CA',
        'employee_count': '67,000+ employees',
        'description': 'Social media, virtual reality, and advertising technology.',
        'career_url': 'https://www.metacareers.com/jobs',
        'url_pattern': '{base_url}?q={query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 1500,
    },
    {
        'name': 'Netflix',
        'industry': 'tech',
        'headquarters': 'Los Gatos, CA',
        'employee_count': '13,000+ employees',
        'description': 'Streaming entertainment and content production.',
        'career_url': 'https://explore.jobs.netflix.net/careers',
        'url_pattern': '{base_url}?query={query}',
        'supports_location': False,
        'display_priority': 20,
        'estimated_open_roles': 400,
    },
    {
        'name': 'Tesla',
        'industry': 'tech',
        'headquarters': 'Austin, TX',
        'employee_count': '130,000+ employees',
        'description': 'Electric vehicles, energy storage, and solar technology.',
        'career_url': 'https://www.tesla.com/careers/search/',
        'url_pattern': '{base_url}?query={query}&location={location}',
        'supports_location': True,
        'display_priority': 15,
        'estimated_open_roles': 3500,
    },
    {
        'name': 'SpaceX',
        'industry': 'tech',
        'headquarters': 'Hawthorne, CA',
        'employee_count': '13,000+ employees',
        'description': 'Aerospace manufacturer and space transportation company.',
        'career_url': 'https://www.spacex.com/careers/',
        'url_pattern': '{base_url}?search={query}',
        'supports_location': False,
        'display_priority': 20,
        'estimated_open_roles': 800,
    },

    # Finance/Banking
    {
        'name': 'Goldman Sachs',
        'industry': 'finance',
        'headquarters': 'New York, NY',
        'employee_count': '45,000+ employees',
        'description': 'Leading global investment banking and financial services.',
        'career_url': 'https://higher.gs.com/results',
        'url_pattern': '{base_url}?q={query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 556,
    },
    {
        'name': 'JPMorgan Chase',
        'industry': 'finance',
        'headquarters': 'New York, NY',
        'employee_count': '310,000+ employees',
        'description': 'Largest bank in the US, offering banking, investment, and asset management.',
        'career_url': 'https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions',
        'url_pattern': '{base_url}?keyword={query}&location={location}',
        'supports_location': True,
        'display_priority': 10,
        'estimated_open_roles': 4900,
    },
    {
        'name': 'Morgan Stanley',
        'industry': 'finance',
        'headquarters': 'New York, NY',
        'employee_count': '80,000+ employees',
        'description': 'Global financial services firm in investment banking and wealth management.',
        'career_url': 'https://morganstanley.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-2/candidate/jobboard/vacancy/1/adv/',
        'url_pattern': '{base_url}?ftq={query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 1200,
    },
    {
        'name': 'Bank of America',
        'industry': 'finance',
        'headquarters': 'Charlotte, NC',
        'employee_count': '210,000+ employees',
        'description': 'Major US banking and financial services corporation.',
        'career_url': 'https://careers.bankofamerica.com/en-us/job-search.html',
        'url_pattern': '{base_url}?ref=search&search=getAllJobs&searchstring={query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 3200,
    },
    {
        'name': 'Citi',
        'industry': 'finance',
        'headquarters': 'New York, NY',
        'employee_count': '240,000+ employees',
        'description': 'Global banking and financial services corporation.',
        'career_url': 'https://jobs.citi.com/search-jobs/',
        'url_pattern': '{base_url}{query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 2800,
    },
    {
        'name': 'BlackRock',
        'industry': 'finance',
        'headquarters': 'New York, NY',
        'employee_count': '19,000+ employees',
        'description': "World's largest asset manager, known for iShares ETFs.",
        'career_url': 'https://careers.blackrock.com/search-jobs/',
        'url_pattern': '{base_url}?keyword={query}',
        'supports_location': False,
        'display_priority': 20,
        'estimated_open_roles': 650,
    },

    # Healthcare
    {
        'name': 'Mayo Clinic',
        'industry': 'healthcare',
        'headquarters': 'Rochester, MN',
        'employee_count': '76,000+ employees',
        'description': 'World-renowned nonprofit medical practice and research center.',
        'career_url': 'https://jobs.mayoclinic.org/search-jobs/',
        'url_pattern': '{base_url}{query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 2100,
    },
    {
        'name': 'Kaiser Permanente',
        'industry': 'healthcare',
        'headquarters': 'Oakland, CA',
        'employee_count': '300,000+ employees',
        'description': 'Integrated managed care consortium and healthcare provider.',
        'career_url': 'https://www.kaiserpermanentejobs.org/search-jobs/',
        'url_pattern': '{base_url}{query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 5000,
    },
    {
        'name': 'HCA Healthcare',
        'industry': 'healthcare',
        'headquarters': 'Nashville, TN',
        'employee_count': '275,000+ employees',
        'description': 'Largest for-profit hospital operator in the United States.',
        'career_url': 'https://careers.hcahealthcare.com/search/',
        'url_pattern': '{base_url}?q={query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 8500,
    },

    # Consulting
    {
        'name': 'McKinsey & Company',
        'industry': 'consulting',
        'headquarters': 'New York, NY',
        'employee_count': '45,000+ employees',
        'description': 'Global management consulting firm serving leading businesses.',
        'career_url': 'https://www.mckinsey.com/careers/search-jobs',
        'url_pattern': '{base_url}?query={query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 800,
    },
    {
        'name': 'Deloitte',
        'industry': 'consulting',
        'headquarters': 'New York, NY',
        'employee_count': '415,000+ employees',
        'description': 'Professional services in consulting, audit, tax, and advisory.',
        'career_url': 'https://apply.deloitte.com/careers/SearchJobs',
        'url_pattern': '{base_url}?keywords={query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 6500,
    },
    {
        'name': 'Accenture',
        'industry': 'consulting',
        'headquarters': 'Dublin, Ireland',
        'employee_count': '740,000+ employees',
        'description': 'Global professional services and consulting company.',
        'career_url': 'https://www.accenture.com/us-en/careers/jobsearch',
        'url_pattern': '{base_url}?query={query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 9000,
    },

    # Aerospace/Defense
    {
        'name': 'Lockheed Martin',
        'industry': 'aerospace',
        'headquarters': 'Bethesda, MD',
        'employee_count': '116,000+ employees',
        'description': 'Aerospace, defense, arms, and security corporation.',
        'career_url': 'https://www.lockheedmartinjobs.com/search-jobs/',
        'url_pattern': '{base_url}{query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 4500,
    },
    {
        'name': 'Boeing',
        'industry': 'aerospace',
        'headquarters': 'Arlington, VA',
        'employee_count': '170,000+ employees',
        'description': 'Aerospace company manufacturing commercial and military aircraft.',
        'career_url': 'https://jobs.boeing.com/search-jobs/',
        'url_pattern': '{base_url}{query}',
        'supports_location': False,
        'display_priority': 10,
        'estimated_open_roles': 3800,
    },
    {
        'name': 'Northrop Grumman',
        'industry': 'aerospace',
        'headquarters': 'Falls Church, VA',
        'employee_count': '95,000+ employees',
        'description': 'Aerospace and defense technology company.',
        'career_url': 'https://www.northropgrumman.com/careers/',
        'url_pattern': '{base_url}?query={query}',
        'supports_location': False,
        'display_priority': 15,
        'estimated_open_roles': 3000,
    },

    # Government
    {
        'name': 'USAJobs',
        'industry': 'government',
        'headquarters': 'Washington, DC',
        'employee_count': 'US Federal Government',
        'description': 'Official job site of the United States federal government.',
        'career_url': 'https://www.usajobs.gov/Search/Results',
        'url_pattern': '{base_url}?k={query}&l={location}',
        'supports_location': True,
        'display_priority': 5,
        'estimated_open_roles': 25000,
    },
]


TITLE_MAPPINGS = [
    {
        'canonical_title': 'Software Engineer',
        'search_aliases': [
            'software engineer', 'software developer', 'software dev',
            'full stack', 'fullstack', 'frontend', 'backend',
            'web developer', 'programmer', 'developer', 'engineer',
            'java developer', 'python developer', 'react developer',
        ],
    },
    {
        'canonical_title': 'DevOps Engineer',
        'search_aliases': [
            'devops', 'dev ops', 'site reliability', 'sre',
            'infrastructure engineer', 'platform engineer',
            'cloud ops', 'cloud engineer',
        ],
    },
    {
        'canonical_title': 'Financial Analyst',
        'search_aliases': [
            'financial analyst', 'finance analyst', 'analyst', 'fp&a',
            'financial planning', 'investment analyst', 'equity analyst',
            'business analyst', 'operations analyst', 'research analyst',
        ],
    },
    {
        'canonical_title': 'Investment Banker',
        'search_aliases': [
            'investment banker', 'investment banking', 'ib analyst',
            'ib associate', 'm&a analyst', 'capital markets',
        ],
    },
    {
        'canonical_title': 'Data Scientist',
        'search_aliases': [
            'data scientist', 'data science', 'machine learning engineer',
            'ml engineer', 'ai engineer', 'data analyst', 'data engineer',
            'data', 'analytics', 'machine learning',
        ],
    },
    {
        'canonical_title': 'Product Manager',
        'search_aliases': [
            'product manager', 'product management', 'pm',
            'product owner', 'technical product manager',
        ],
    },
    {
        'canonical_title': 'Registered Nurse',
        'search_aliases': [
            'registered nurse', 'rn', 'nurse', 'nurse practitioner',
            'np', 'clinical nurse',
        ],
    },
    {
        'canonical_title': 'Marketing Manager',
        'search_aliases': [
            'marketing manager', 'marketing', 'digital marketing',
            'growth marketing', 'brand manager', 'content marketing',
        ],
    },
    {
        'canonical_title': 'UX Designer',
        'search_aliases': [
            'ux designer', 'ui designer', 'ux/ui', 'product designer',
            'interaction designer', 'user experience', 'designer',
            'graphic designer', 'visual designer',
        ],
    },
    {
        'canonical_title': 'Project Manager',
        'search_aliases': [
            'project manager', 'program manager', 'scrum master',
            'agile coach', 'delivery manager',
        ],
    },
    {
        'canonical_title': 'Accountant',
        'search_aliases': [
            'accountant', 'accounting', 'cpa', 'tax accountant',
            'auditor', 'bookkeeper',
        ],
    },
    {
        'canonical_title': 'Sales Representative',
        'search_aliases': [
            'sales rep', 'sales representative', 'account executive',
            'ae', 'business development', 'bdr', 'sdr', 'sales',
            'account manager', 'customer success',
        ],
    },
    {
        'canonical_title': 'Human Resources',
        'search_aliases': [
            'human resources', 'hr', 'hr manager', 'talent acquisition',
            'recruiter', 'people operations', 'hiring manager',
        ],
    },
]


# employer name -> list of canonical categories they hire for
EMPLOYER_CATEGORIES = {
    'Google': ['Software Engineer', 'DevOps Engineer', 'Product Manager', 'Data Scientist', 'UX Designer', 'Marketing Manager'],
    'Apple': ['Software Engineer', 'Product Manager', 'UX Designer', 'Data Scientist', 'Marketing Manager'],
    'Amazon': ['Software Engineer', 'DevOps Engineer', 'Data Scientist', 'Product Manager', 'Project Manager', 'Sales Representative'],
    'Microsoft': ['Software Engineer', 'DevOps Engineer', 'Product Manager', 'Data Scientist', 'UX Designer', 'Project Manager'],
    'Meta': ['Software Engineer', 'Product Manager', 'Data Scientist', 'UX Designer', 'Marketing Manager'],
    'Netflix': ['Software Engineer', 'Data Scientist', 'Product Manager', 'UX Designer'],
    'Tesla': ['Software Engineer', 'DevOps Engineer', 'Project Manager', 'Data Scientist'],
    'SpaceX': ['Software Engineer', 'DevOps Engineer', 'Project Manager'],
    'Goldman Sachs': ['Financial Analyst', 'Investment Banker', 'Software Engineer', 'Data Scientist', 'Human Resources'],
    'JPMorgan Chase': ['Financial Analyst', 'Investment Banker', 'Software Engineer', 'Data Scientist', 'Project Manager', 'Human Resources'],
    'Morgan Stanley': ['Financial Analyst', 'Investment Banker', 'Software Engineer', 'Data Scientist'],
    'Bank of America': ['Financial Analyst', 'Investment Banker', 'Software Engineer', 'Sales Representative', 'Human Resources'],
    'Citi': ['Financial Analyst', 'Investment Banker', 'Software Engineer', 'Data Scientist'],
    'BlackRock': ['Financial Analyst', 'Investment Banker', 'Software Engineer', 'Data Scientist'],
    'Mayo Clinic': ['Registered Nurse', 'Data Scientist', 'Software Engineer', 'Project Manager'],
    'Kaiser Permanente': ['Registered Nurse', 'Software Engineer', 'Project Manager', 'Human Resources'],
    'HCA Healthcare': ['Registered Nurse', 'Project Manager', 'Human Resources', 'Accountant'],
    'McKinsey & Company': ['Financial Analyst', 'Data Scientist', 'Software Engineer'],
    'Deloitte': ['Financial Analyst', 'Accountant', 'Software Engineer', 'Data Scientist', 'Human Resources'],
    'Accenture': ['Software Engineer', 'Data Scientist', 'Project Manager', 'Product Manager', 'DevOps Engineer'],
    'Lockheed Martin': ['Software Engineer', 'DevOps Engineer', 'Project Manager', 'Data Scientist'],
    'Boeing': ['Software Engineer', 'Project Manager', 'Data Scientist', 'DevOps Engineer'],
    'Northrop Grumman': ['Software Engineer', 'DevOps Engineer', 'Project Manager', 'Data Scientist'],
    'USAJobs': ['Software Engineer', 'Financial Analyst', 'Registered Nurse', 'Project Manager', 'Human Resources', 'Accountant'],
}


# (employer_name, canonical_title) -> preferred_search_term
TITLE_OVERRIDES = [
    ('Google', 'DevOps Engineer', 'site reliability engineer'),
    ('Goldman Sachs', 'Financial Analyst', 'analyst finance'),
    ('Goldman Sachs', 'Investment Banker', 'investment banking analyst'),
    ('Amazon', 'DevOps Engineer', 'systems dev engineer devops'),
    ('McKinsey & Company', 'Financial Analyst', 'business analyst'),
]


class Command(BaseCommand):
    help = 'Seed the employer directory with initial data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding employer directory...\n')

        # 1. Seed employers
        employer_count = 0
        for data in EMPLOYERS:
            emp, created = FeaturedEmployer.objects.update_or_create(
                name=data['name'],
                defaults=data,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} employer: {emp.name}')
            employer_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n  {employer_count} employers seeded.\n'))

        # 2. Seed title mappings
        mapping_count = 0
        for data in TITLE_MAPPINGS:
            mapping, created = JobTitleMapping.objects.update_or_create(
                canonical_title=data['canonical_title'],
                defaults={'search_aliases': data['search_aliases']},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} title mapping: {mapping.canonical_title}')
            mapping_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n  {mapping_count} title mappings seeded.\n'))

        # 3. Seed employer categories
        cat_count = 0
        for employer_name, categories in EMPLOYER_CATEGORIES.items():
            try:
                employer = FeaturedEmployer.objects.get(name=employer_name)
            except FeaturedEmployer.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'  Employer not found: {employer_name}'))
                continue

            for cat_name in categories:
                _, created = DirectoryEmployerCategory.objects.update_or_create(
                    employer=employer,
                    canonical_category=cat_name,
                    defaults={'is_active': True},
                )
                cat_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n  {cat_count} employer-category mappings seeded.\n'))

        # 4. Seed title overrides
        override_count = 0
        for employer_name, title_name, preferred_term in TITLE_OVERRIDES:
            try:
                employer = FeaturedEmployer.objects.get(name=employer_name)
                mapping = JobTitleMapping.objects.get(canonical_title=title_name)
            except (FeaturedEmployer.DoesNotExist, JobTitleMapping.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(
                    f'  Override skip ({employer_name} / {title_name}): {e}'
                ))
                continue

            _, created = EmployerTitleOverride.objects.update_or_create(
                employer=employer,
                canonical_title=mapping,
                defaults={'preferred_search_term': preferred_term},
            )
            override_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n  {override_count} title overrides seeded.\n'))
        self.stdout.write(self.style.SUCCESS('Directory seeding complete!'))
