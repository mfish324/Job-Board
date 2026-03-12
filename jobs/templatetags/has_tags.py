"""
Template tags for Hiring Activity Score (HAS) display.

Usage in templates:
    {% load has_tags %}

    {{ listing|has_score_pips }}
    {{ listing|source_badge }}
    {{ score|score_band_badge }}
    {% has_tooltip listing %}
"""

import re

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import format_html
import bleach

register = template.Library()

# Allowed tags/attributes for safe_description
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'span', 'div',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
]
ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'span': ['class'],
    'div': ['class'],
}


@register.filter
def safe_description(value):
    """
    Sanitize HTML description using bleach to prevent XSS.

    Usage:
        {{ listing.description|safe_description }}
    """
    if not value:
        return ''
    cleaned = bleach.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )
    return mark_safe(cleaned)


@register.filter
def clean_snippet(value):
    """
    Strip HTML tags while preserving word boundaries, then collapse whitespace.
    Unlike Django's striptags, this inserts a space where tags are removed
    so "First</li><li>Second" becomes "First Second" instead of "FirstSecond".

    Usage:
        {{ listing.description|clean_snippet|truncatewords:25 }}
    """
    if not value:
        return ''
    text = str(value)
    # Insert a space before closing block-level tags and between adjacent tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Collapse multiple whitespace into single spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


@register.filter
def has_score_pips(listing_or_score):
    """
    Display the HAS score as a pip indicator (●●●●○).

    Usage:
        {{ listing|has_score_pips }}
        {{ score_value|has_score_pips }}

    Score mapping:
        80-100: ●●●●● (5 pips)
        60-79:  ●●●●○ (4 pips)
        40-59:  ●●●○○ (3 pips)
        20-39:  ●●○○○ (2 pips)
        0-19:   ●○○○○ (1 pip)
    """
    # Handle both listing objects and raw score values
    if hasattr(listing_or_score, 'activity_score'):
        try:
            score = listing_or_score.activity_score.total_score
        except Exception:
            return mark_safe('<span class="text-muted">—</span>')
    else:
        score = int(listing_or_score) if listing_or_score else 0

    # Calculate pip count (1-5)
    if score >= 80:
        filled = 5
        color = 'success'
    elif score >= 60:
        filled = 4
        color = 'success'
    elif score >= 40:
        filled = 3
        color = 'warning'
    elif score >= 20:
        filled = 2
        color = 'warning'
    else:
        filled = 1
        color = 'danger'

    empty = 5 - filled

    pips = (
        f'<span class="text-{color}">{"●" * filled}</span>'
        f'<span class="text-muted">{"○" * empty}</span>'
    )

    return mark_safe(
        f'<span class="has-pips" title="Hiring Activity Score: {score}/100">{pips}</span>'
    )


@register.filter
def source_badge(listing_or_source):
    """
    Display a source badge for a job listing.

    Usage:
        {{ listing|source_badge }}
        {{ "verified"|source_badge }}

    Returns appropriate badge for:
        - verified: Green badge with checkmark (for employer-posted jobs)
        - scraped: Blue badge with eye icon (for market-observed listings)
    """
    # Determine source type
    if hasattr(listing_or_source, 'source_ats'):
        # It's a ScrapedJobListing
        return mark_safe(
            '<span class="badge bg-info">'
            '<i class="bi bi-eye"></i> Market-Observed'
            '</span>'
        )
    elif hasattr(listing_or_source, 'posted_by'):
        # It's a regular Job posted by employer
        return mark_safe(
            '<span class="badge bg-success">'
            '<i class="bi bi-patch-check-fill"></i> Verified Employer'
            '</span>'
        )
    elif listing_or_source == 'verified':
        return mark_safe(
            '<span class="badge bg-success">'
            '<i class="bi bi-patch-check-fill"></i> Verified Employer'
            '</span>'
        )
    elif listing_or_source == 'scraped':
        return mark_safe(
            '<span class="badge bg-info">'
            '<i class="bi bi-eye"></i> Market-Observed'
            '</span>'
        )

    return ''


@register.filter
def score_band_badge(score_or_band):
    """
    Display a badge for the score band.

    Usage:
        {{ listing.activity_score.score_band|score_band_badge }}
        {{ "very_active"|score_band_badge }}
    """
    # Handle HiringActivityScore objects
    if hasattr(score_or_band, 'score_band'):
        band = score_or_band.score_band
        score = score_or_band.total_score
    elif hasattr(score_or_band, 'activity_score'):
        try:
            band = score_or_band.activity_score.score_band
            score = score_or_band.activity_score.total_score
        except Exception:
            return ''
    else:
        band = str(score_or_band)
        score = None

    badge_config = {
        'very_active': ('success', 'Very Active', 'bi-lightning-charge-fill'),
        'likely_active': ('primary', 'Likely Active', 'bi-check-circle'),
        'uncertain': ('warning', 'Uncertain', 'bi-question-circle'),
        'low_signal': ('secondary', 'Low Signal', 'bi-exclamation-circle'),
    }

    config = badge_config.get(band, ('secondary', band.replace('_', ' ').title(), 'bi-circle'))
    color, label, icon = config

    score_text = f' ({score})' if score is not None else ''

    return mark_safe(
        f'<span class="badge bg-{color}">'
        f'<i class="bi {icon}"></i> {label}{score_text}'
        f'</span>'
    )


@register.filter
def ats_badge(source_ats):
    """
    Display a badge for the ATS source.

    Usage:
        {{ listing.source_ats|ats_badge }}
    """
    ats_names = {
        'greenhouse': ('Greenhouse', 'success'),
        'lever': ('Lever', 'primary'),
        'workday': ('Workday', 'info'),
        'icims': ('iCIMS', 'warning'),
        'taleo': ('Taleo', 'secondary'),
        'bamboohr': ('BambooHR', 'success'),
        'ashby': ('Ashby', 'primary'),
        'jobvite': ('Jobvite', 'info'),
        'smartrecruiters': ('SmartRecruiters', 'warning'),
        'other': ('Other', 'secondary'),
    }

    name, color = ats_names.get(source_ats, (source_ats, 'secondary'))

    return mark_safe(
        f'<span class="badge bg-{color}-subtle text-{color}">{name}</span>'
    )


@register.simple_tag
def has_tooltip(listing):
    """
    Generate a tooltip with HAS score breakdown.

    Usage:
        {% has_tooltip listing %}
    """
    try:
        has = listing.activity_score
    except Exception:
        return ''

    breakdown = has.score_breakdown
    if not breakdown:
        return ''

    # Build tooltip content
    lines = [f'<strong>Score: {has.total_score}/100</strong>', '']

    for signal, data in breakdown.items():
        points = data.get('points', 0)
        if points == 0 and signal != 'base':
            continue

        prefix = '+' if points > 0 else ''
        explanation = data.get('explanation', '')

        # Format signal name nicely
        signal_name = signal.replace('_', ' ').title()
        lines.append(f'{signal_name}: {prefix}{points}')
        if explanation:
            lines.append(f'  ({explanation})')

    tooltip_content = '<br>'.join(lines)

    return mark_safe(
        f'<span data-bs-toggle="tooltip" data-bs-html="true" '
        f'title="{tooltip_content}" style="cursor: help;">'
        f'<i class="bi bi-info-circle text-muted"></i>'
        f'</span>'
    )


@register.inclusion_tag('jobs/partials/has_indicator.html')
def has_indicator(listing, show_tooltip=True):
    """
    Render the full HAS indicator component.

    Usage:
        {% has_indicator listing %}
        {% has_indicator listing show_tooltip=False %}
    """
    try:
        has = listing.activity_score
        score = has.total_score
        band = has.score_band
        breakdown = has.score_breakdown
    except Exception:
        score = None
        band = None
        breakdown = {}

    return {
        'listing': listing,
        'score': score,
        'band': band,
        'breakdown': breakdown,
        'show_tooltip': show_tooltip,
    }


@register.filter
def days_ago(date_value):
    """
    Display how many days ago a date was.

    Usage:
        {{ listing.date_first_seen|days_ago }}
    """
    from django.utils import timezone

    if not date_value:
        return ''

    delta = timezone.now() - date_value
    days = delta.days

    if days == 0:
        return 'today'
    elif days == 1:
        return '1 day ago'
    else:
        return f'{days} days ago'


@register.filter
def has_pip_count(score):
    """
    Maps 0-100 HAS score to 1-5 filled pips.

    Usage:
        {{ score|has_pip_count }}
    """
    try:
        score = int(score)
    except (TypeError, ValueError):
        return 1
    if score >= 80:
        return 5
    if score >= 65:
        return 4
    if score >= 50:
        return 3
    if score >= 35:
        return 2
    return 1


@register.filter
def format_salary(listing):
    """
    Format salary range nicely.

    Usage:
        {{ listing|format_salary }}
    """
    if not hasattr(listing, 'salary_min') and not hasattr(listing, 'salary_max'):
        return ''

    salary_min = getattr(listing, 'salary_min', None)
    salary_max = getattr(listing, 'salary_max', None)
    currency = getattr(listing, 'salary_currency', 'USD')

    if not salary_min and not salary_max:
        return ''

    def format_num(n):
        if n >= 1000:
            return f'{n/1000:.0f}K'
        return str(int(n))

    if salary_min and salary_max:
        return f'${format_num(salary_min)} - ${format_num(salary_max)} {currency}'
    elif salary_min:
        return f'From ${format_num(salary_min)} {currency}'
    else:
        return f'Up to ${format_num(salary_max)} {currency}'
