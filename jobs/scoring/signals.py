"""
Hiring Activity Score (HAS) Signal Calculators

Individual signal calculation functions for the HAS algorithm.
Each function returns (points, explanation) tuple.
"""

from datetime import timedelta
from django.utils import timezone


def calculate_freshness(listing, config):
    """
    Calculate freshness score based on how recently the listing was posted.
    Linear decay from max_points to 0 over decay_days.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['freshness']
    max_points = cfg['max_points']
    decay_days = cfg['decay_days']

    days_open = listing.days_since_first_seen()

    if days_open <= 0:
        return max_points, "Just posted"

    if days_open >= decay_days:
        return 0, f"Posted {days_open} days ago (fully decayed)"

    # Linear decay
    points = max_points * (1 - (days_open / decay_days))
    points = round(points, 1)

    return points, f"Posted {days_open} days ago"


def calculate_specificity(listing, config):
    """
    Calculate specificity score based on listing completeness.
    Awards points for salary info, location, and description quality.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['specificity']
    points = 0
    details = []

    # Salary info
    if listing.salary_min or listing.salary_max:
        points += cfg['has_salary']
        details.append("has salary")

    # Location specificity
    if listing.location and len(listing.location) > 5:
        points += cfg['has_location']
        details.append("has location")

    # Description quality (length as proxy)
    desc_len = len(listing.description) if listing.description else 0
    min_len = cfg['min_description_length']

    if desc_len >= min_len:
        points += cfg['description_quality']
        details.append(f"quality description ({desc_len} chars)")
    elif desc_len > 0:
        # Partial credit
        partial = cfg['description_quality'] * (desc_len / min_len)
        points += round(partial, 1)
        details.append(f"partial description ({desc_len} chars)")

    points = min(points, cfg['max_points'])
    explanation = ", ".join(details) if details else "minimal info"

    return round(points, 1), explanation


def calculate_company_velocity(listing, config, profile=None):
    """
    Calculate company velocity score based on net job movement.
    Positive movement suggests active hiring.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['company_velocity']
    max_points = cfg['max_points']

    if not profile:
        return 0, "No company profile"

    net_movement = profile.net_job_movement_30d

    if net_movement <= 0:
        return 0, f"Net movement: {net_movement}"

    points = min(net_movement * cfg['positive_per_job'], max_points)

    return round(points, 1), f"Net +{net_movement} jobs in 30d"


def calculate_ats_behavior(listing, config):
    """
    Calculate ATS behavior score based on listing changes.
    Awards points for description updates and similar role closures.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['ats_behavior']
    points = 0
    details = []

    # Check if description was updated recently (via repost_count or hash changes)
    # This would require tracking description history - simplified for now
    if listing.repost_count > 0:
        # Reposting with changes is a positive signal (not evergreen)
        points += cfg['description_updated']
        details.append("description updated")

    # Similar role closures would require checking other listings
    # Simplified: check if company has closed listings recently
    if listing.company:
        closed_recently = listing.company.scraped_listings.filter(
            status='closed',
            date_removed__gte=timezone.now() - timedelta(days=30)
        ).exists()

        if closed_recently:
            points += cfg['similar_role_closed']
            details.append("company closing roles")

    points = min(points, cfg['max_points'])
    explanation = ", ".join(details) if details else "no ATS signals"

    return round(points, 1), explanation


def calculate_company_reputation(listing, config, profile=None):
    """
    Calculate company reputation adjustment.
    Good reputation = positive, bad reputation = negative.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['company_reputation']

    if not profile:
        return 0, "No company profile"

    rep_score = profile.reputation_score

    if rep_score >= cfg['good_reputation_threshold']:
        # Scale from 0 to max based on how far above threshold
        excess = rep_score - cfg['good_reputation_threshold']
        max_excess = 100 - cfg['good_reputation_threshold']
        points = (excess / max_excess) * cfg['max_points']
        return round(points, 1), f"Good reputation ({rep_score})"

    elif rep_score <= cfg['bad_reputation_threshold']:
        # Scale from 0 to min based on how far below threshold
        deficit = cfg['bad_reputation_threshold'] - rep_score
        points = -(deficit / cfg['bad_reputation_threshold']) * abs(cfg['min_points'])
        return round(points, 1), f"Poor reputation ({rep_score})"

    return 0, f"Neutral reputation ({rep_score})"


def calculate_industry_adjustment(listing, config, profile=None):
    """
    Calculate industry-based adjustment.
    Slow industries get bonus, fast industries get penalty for old listings.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['industry_adjustment']

    industry = None
    if profile and profile.company:
        industry = profile.company.industry.lower() if profile.company.industry else None
    elif listing.company:
        industry = listing.company.industry.lower() if listing.company.industry else None

    if not industry:
        return 0, "Unknown industry"

    days_open = listing.days_since_first_seen()

    # Slow industries get bonus - they normally have longer hiring cycles
    if any(ind in industry for ind in cfg['slow_industries']):
        if days_open > 30:
            return cfg['slow_bonus'], f"Slow-hiring industry ({industry})"
        return round(cfg['slow_bonus'] / 2, 1), f"Slow-hiring industry ({industry})"

    # Fast industries get penalty if listing is old
    if any(ind in industry for ind in cfg['fast_industries']):
        if days_open > 14:
            return cfg['fast_penalty'], f"Fast-hiring industry, old listing ({industry})"
        return 0, f"Fast-hiring industry ({industry})"

    return 0, f"Standard industry ({industry})"


def calculate_repost_penalty(listing, config):
    """
    Calculate penalty for repeated reposts.
    Each repost without filling = -5 points.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['repost_penalty']

    if listing.repost_count == 0:
        return 0, "No reposts"

    penalty = max(
        listing.repost_count * cfg['points_per_repost'],
        cfg['min_points']
    )

    return round(penalty, 1), f"{listing.repost_count} repost(s)"


def calculate_evergreen_penalty(listing, config):
    """
    Calculate penalty for evergreen listings (open 90+ days unchanged).

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['evergreen_penalty']
    threshold = cfg['threshold_days']

    days_open = listing.days_since_first_seen()

    if days_open < threshold:
        return 0, f"Open {days_open} days (under {threshold}d threshold)"

    # Base penalty for being evergreen
    base_penalty = cfg['min_points'] * 0.5

    # Extra penalty if no description changes (repost_count = 0 indicates no changes)
    if listing.repost_count == 0:
        base_penalty *= cfg['no_change_multiplier']

    penalty = max(base_penalty, cfg['min_points'])

    return round(penalty, 1), f"Evergreen listing ({days_open} days, {listing.repost_count} updates)"


def calculate_boilerplate_penalty(listing, config, profile=None):
    """
    Calculate penalty for high boilerplate ratio (templated listings).

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['boilerplate_penalty']

    if not profile:
        return 0, "No company profile"

    ratio = profile.boilerplate_ratio
    threshold = cfg['high_ratio_threshold']

    if ratio < threshold:
        return 0, f"Boilerplate ratio: {ratio:.0%}"

    # Scale penalty based on how far above threshold
    excess = ratio - threshold
    max_excess = 1.0 - threshold
    penalty = (excess / max_excess) * cfg['min_points']

    return round(penalty, 1), f"High boilerplate ({ratio:.0%})"


def calculate_stale_penalty(listing, config):
    """
    Calculate penalty if listing hasn't been seen recently.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['stale_penalty']
    threshold = cfg['stale_threshold_days']

    days_since_seen = (timezone.now() - listing.date_last_seen).days

    if days_since_seen < threshold:
        return 0, f"Last seen {days_since_seen} days ago"

    # Scale penalty based on staleness
    excess_days = days_since_seen - threshold
    penalty = max(
        -min(excess_days, 10),  # Cap at 10 days excess
        cfg['min_points']
    )

    return round(penalty, 1), f"Stale ({days_since_seen} days since last seen)"
