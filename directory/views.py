from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404

from .models import FeaturedEmployer, DirectoryEmployerCategory, DirectoryClick
from .utils import build_deep_link, match_title


def directory_index(request):
    # Server-side industry filter. Default to TECHNOLOGY when no param is
    # present so first-time visitors land on the audience we're optimizing for.
    # Use 'all' explicitly to see every employer.
    industry_filter = request.GET.get('industry')
    if industry_filter is None:
        industry_filter = 'TECHNOLOGY'

    employers = FeaturedEmployer.objects.filter(is_active=True).prefetch_related('categories')
    if industry_filter != 'all':
        employers = employers.filter(industry=industry_filter)

    # Pre-join counts per industry for chip labels — one aggregate query.
    from django.db.models import Count
    counts = dict(
        FeaturedEmployer.objects.filter(is_active=True)
        .values_list('industry')
        .annotate(c=Count('id'))
        .values_list('industry', 'c')
    )
    chips = [
        {'value': value, 'label': label, 'count': counts.get(value, 0)}
        for value, label in FeaturedEmployer.INDUSTRY_CHOICES
    ]

    context = {
        'employers': employers,
        'chips': chips,
        'current_industry': industry_filter,
        'total_count': sum(counts.values()),
    }
    return render(request, 'directory/index.html', context)


def employer_detail(request, slug):
    employer = get_object_or_404(FeaturedEmployer, slug=slug, is_active=True)
    categories = DirectoryEmployerCategory.objects.filter(
        employer=employer, is_active=True
    ).order_by('-estimated_count')

    # Build deep-link for each category
    category_links = []
    for cat in categories:
        mapping, _ = match_title(cat.canonical_category)
        link = build_deep_link(employer, cat.canonical_category, '', mapping)
        category_links.append({
            'category': cat,
            'deep_link': link,
        })

    # Check if user came from search (for contextual info)
    last_search = request.GET.get('q', '')

    context = {
        'employer': employer,
        'category_links': category_links,
        'last_search': last_search,
    }
    return render(request, 'directory/employer_detail.html', context)


def employer_redirect(request, slug):
    """Redirect to employer's career site and log the click."""
    employer = get_object_or_404(FeaturedEmployer, slug=slug, is_active=True)
    query = request.GET.get('q', '')
    location = request.GET.get('location', '')
    source = request.GET.get('source', 'directory_page')

    # Match title for override lookup
    mapping, _ = match_title(query)
    url = build_deep_link(employer, query, location, mapping)

    # Log click. Snapshot employer.industry now so analytics survive later
    # industry retags.
    DirectoryClick.objects.create(
        employer=employer,
        industry=employer.industry,
        search_query=query,
        location=location,
        category=mapping,
        source=source,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
    )

    return redirect(url)
