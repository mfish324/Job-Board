import re
from urllib.parse import quote_plus

from .models import FeaturedEmployer, JobTitleMapping, EmployerTitleOverride, DirectoryEmployerCategory


def match_title(raw_query):
    """
    Match a user's raw search string to the best canonical JobTitleMapping.

    Strategy: check each mapping's aliases for substring presence in the query.
    Prefer the longest alias match for specificity.

    Returns (JobTitleMapping, matched_alias) or (None, None).
    """
    if not raw_query:
        return None, None

    normalized = re.sub(r'\s+', ' ', raw_query.lower().strip())
    best_mapping = None
    best_alias = ''

    for mapping in JobTitleMapping.objects.all():
        for alias in (mapping.search_aliases or []):
            alias_lower = alias.lower().strip()
            if alias_lower and alias_lower in normalized:
                if len(alias_lower) > len(best_alias):
                    best_mapping = mapping
                    best_alias = alias_lower

    return best_mapping, best_alias if best_mapping else (None, None)


def build_deep_link(employer, query='', location='', canonical_title=None):
    """
    Construct a deep-link URL for a given employer + search query + location.

    1. Check EmployerTitleOverride for employer + canonical_title
    2. Check DirectoryEmployerCategory for employer_search_term
    3. Fall back to raw query
    4. URL-encode and fill the employer's URL pattern
    """
    search_term = query

    if canonical_title:
        # Check for employer-specific override
        try:
            override = EmployerTitleOverride.objects.get(
                employer=employer, canonical_title=canonical_title
            )
            search_term = override.preferred_search_term
        except EmployerTitleOverride.DoesNotExist:
            # Check category mapping
            try:
                cat = DirectoryEmployerCategory.objects.get(
                    employer=employer,
                    canonical_category=canonical_title.canonical_title
                )
                if cat.employer_search_term:
                    search_term = cat.employer_search_term
            except DirectoryEmployerCategory.DoesNotExist:
                pass

    encoded_query = quote_plus(search_term)
    encoded_location = quote_plus(location) if location else ''

    try:
        url = employer.url_pattern.format(
            base_url=employer.career_url.rstrip('/'),
            query=encoded_query,
            location=encoded_location,
        )
    except (KeyError, IndexError):
        # Fallback: just append query to career URL
        url = f'{employer.career_url}?q={encoded_query}'

    return url


def get_directory_results(search_query, location='', limit=6):
    """
    Given a user's search query, find matching directory employers.

    Returns list of dicts with employer info and deep-link URLs.
    """
    mapping, alias = match_title(search_query)
    if not mapping:
        return [], None

    # Find employers with this category active
    categories = DirectoryEmployerCategory.objects.filter(
        canonical_category=mapping.canonical_title,
        is_active=True,
        employer__is_active=True,
    ).select_related('employer').order_by(
        'employer__display_priority', '-estimated_count'
    )[:limit]

    results = []
    for cat in categories:
        employer = cat.employer
        deep_link = build_deep_link(employer, search_query, location, mapping)
        results.append({
            'employer': employer,
            'category': cat,
            'deep_link': deep_link,
            'role_count': cat.estimated_count,
            'canonical_title': mapping,
        })

    return results, mapping
