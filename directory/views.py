from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404

from .models import FeaturedEmployer, DirectoryEmployerCategory, DirectoryClick
from .utils import build_deep_link, match_title


def directory_index(request):
    employers = FeaturedEmployer.objects.filter(is_active=True).prefetch_related('categories')
    industries = FeaturedEmployer.INDUSTRY_CHOICES

    context = {
        'employers': employers,
        'industries': industries,
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

    # Log click
    DirectoryClick.objects.create(
        employer=employer,
        search_query=query,
        location=location,
        category=mapping,
        source=source,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
    )

    return redirect(url)
