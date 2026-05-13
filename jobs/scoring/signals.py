"""
Hiring Activity Score (HAS) Signal Calculators

Individual signal calculation functions for the HAS algorithm.
Each function returns (points, explanation) tuple.
"""

from datetime import timedelta
from django.utils import timezone


def _normalize_company_name(name):
    """Normalize a company name for cache lookup. Lowercased, stripped."""
    if not name:
        return ''
    return name.lower().strip()


def _diversity_factor(listing, config, diversity_map):
    """
    Returns (multiplier, ratio_or_none).
    multiplier scales the velocity bonus: low-diversity (template-farm) companies
    get a smaller multiplier. ratio is the raw diversity (distinct_hashes/total)
    or None if the company has too few listings to evaluate.
    """
    cfg = config.get('template_farm', {})
    if diversity_map is None:
        return 1.0, None
    name = _normalize_company_name(listing.company_name)
    entry = diversity_map.get(name)
    if not entry:
        return 1.0, None
    distinct, total = entry
    if total < cfg.get('min_listings', 5):
        return 1.0, None
    ratio = distinct / total if total else 1.0
    scale = min(1.0, ratio * cfg.get('velocity_scale_factor', 1.5))
    return scale, ratio


def _age_decay_factor(listing, config):
    """
    Linear decay factor [0, 1] based on listing age vs freshness.decay_days.
    Used to scale company-level bonuses (velocity, reputation) so that an old
    listing doesn't get full credit for the company's current hiring activity.
    """
    decay_days = config.get('freshness', {}).get('decay_days', 60)
    if decay_days <= 0:
        return 1.0
    days_open = listing.days_since_first_seen()
    if days_open <= 0:
        return 1.0
    if days_open >= decay_days:
        return 0.0
    return 1 - (days_open / decay_days)


def calculate_freshness(listing, config):
    """
    Calculate freshness score based on how recently the listing was posted.

    Default behavior: linear decay from max_points to 0 over decay_days.

    If `decay_start_day` is set (e.g. tech profile = 14), the score stays flat
    at max_points until that day, then decays linearly to 0 by `decay_days`.
    This lets per-industry profiles tighten the curve for industries where
    untouched listings are stronger ghost-job signals.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['freshness']
    max_points = cfg['max_points']
    decay_days = cfg['decay_days']
    decay_start = cfg.get('decay_start_day', 0)

    days_open = listing.days_since_first_seen()

    if days_open <= decay_start:
        return max_points, f"Just posted ({days_open}d, flat to {decay_start}d)" if decay_start else "Just posted"

    if days_open >= decay_days:
        return 0, f"Posted {days_open} days ago (fully decayed at {decay_days}d)"

    # Linear decay over the [decay_start, decay_days] window.
    decay_range = decay_days - decay_start
    elapsed = days_open - decay_start
    points = max_points * (1 - (elapsed / decay_range))
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

    # Tools/stack mentions (industry-profile opt-in; default 0 = no-op).
    # Tech profile rewards listings that name a real stack (skills_count >= N).
    tools_pts = cfg.get('tools_stack', 0)
    if tools_pts:
        min_tools = cfg.get('min_tools_count', 5)
        skills_count = getattr(listing, 'skills_count', 0) or 0
        if skills_count >= min_tools:
            points += tools_pts
            details.append(f"named stack ({skills_count} tools)")

    points = min(points, cfg['max_points'])
    explanation = ", ".join(details) if details else "minimal info"

    return round(points, 1), explanation


def calculate_company_velocity(listing, config, velocity_map=None, diversity_map=None):
    """
    Calculate company velocity from new-listing volume in the lookback window.
    Counts distinct ScrapedJobListing rows for this company_name with
    date_first_seen within `lookback_days`. Tiers map count → points.

    Args:
        velocity_map: optional dict[normalized_name -> count] for batch scoring.
            If None, computes inline (single-listing path).
    """
    cfg = config['company_velocity']
    max_points = cfg['max_points']
    lookback = cfg.get('lookback_days', 30)

    name = _normalize_company_name(listing.company_name)
    if not name:
        return 0, "No company name"

    if velocity_map is not None:
        count = velocity_map.get(name, 0)
    else:
        from django.db.models.functions import Lower, Trim
        from jobs.models import ScrapedJobListing
        cutoff = timezone.now() - timedelta(days=lookback)
        count = (
            ScrapedJobListing.objects
            .annotate(_norm=Lower(Trim('company_name')))
            .filter(_norm=name, date_first_seen__gte=cutoff)
            .count()
        )

    if count <= 0:
        return 0, f"No new listings in {lookback}d"

    points = 0
    for threshold, pts in cfg.get('tiers', []):
        if count >= threshold:
            points = pts
            break
    points = min(points, max_points)

    # Scale by listing age — an old listing doesn't get full credit for
    # the company's current hiring activity.
    decay = _age_decay_factor(listing, config)
    diversity_scale, ratio = _diversity_factor(listing, config, diversity_map)
    scaled = round(points * decay * diversity_scale, 1)
    age = listing.days_since_first_seen()
    if ratio is not None and diversity_scale < 1.0:
        return scaled, (
            f"{count} new in {lookback}d (×{decay:.2f} age {age}d, "
            f"×{diversity_scale:.2f} diversity {ratio:.0%})"
        )
    return scaled, f"{count} new listings in {lookback}d (×{decay:.2f} age {age}d)"


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


def calculate_company_reputation(listing, config, featured_set=None):
    """
    Calculate company reputation bonus based on curated lists:
      - FeaturedEmployer directory entries (loaded into `featured_set`)
      - `overrides` map in config (lowercased company_name → tier 1 or 2)

    Args:
        featured_set: optional set of normalized FeaturedEmployer names. If None,
            queries FeaturedEmployer inline (single-listing path).
    """
    cfg = config['company_reputation']
    name = _normalize_company_name(listing.company_name)
    if not name:
        return 0, "No company name"

    if featured_set is None:
        try:
            from directory.models import FeaturedEmployer
            featured_set = {
                _normalize_company_name(fe_name)
                for fe_name in FeaturedEmployer.objects.values_list('name', flat=True)
            }
        except Exception:
            featured_set = set()

    base_pts = 0
    label = None
    if name in featured_set:
        base_pts = cfg.get('featured_employer_bonus', 8)
        label = "Featured employer"
    else:
        tier = cfg.get('overrides', {}).get(name)
        if tier == 1:
            base_pts = cfg.get('tier_1_bonus', 8)
            label = "Tier 1 reputable"
        elif tier == 2:
            base_pts = cfg.get('tier_2_bonus', 4)
            label = "Tier 2 reputable"

    if base_pts <= 0:
        return 0, "Standard company"

    # Scale by listing age — reputation reflects the company, but the listing
    # itself fades in relevance as it ages.
    decay = _age_decay_factor(listing, config)
    scaled = round(base_pts * decay, 1)
    age = listing.days_since_first_seen()
    return scaled, f"{label} ({listing.company_name}) ×{decay:.2f} age {age}d"


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
    Each repost without filling = -5 points by default.

    A `penalty_multiplier` in the config scales both the per-repost penalty
    and the floor — used by the tech profile (×1.5) where identical reposting
    is a stronger ghost-job indicator.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config['repost_penalty']

    if listing.repost_count == 0:
        return 0, "No reposts"

    multiplier = cfg.get('penalty_multiplier', 1.0)
    per_repost = cfg['points_per_repost'] * multiplier
    floor = cfg['min_points'] * multiplier

    penalty = max(listing.repost_count * per_repost, floor)

    if multiplier != 1.0:
        return round(penalty, 1), f"{listing.repost_count} repost(s) ×{multiplier} multiplier"
    return round(penalty, 1), f"{listing.repost_count} repost(s)"


def calculate_template_farm_penalty(listing, config, diversity_map=None):
    """
    Explicit penalty when a company's listing pool has very low description-hash
    diversity (indicating mass-posted templates). This is in addition to the
    velocity scaling already applied in calculate_company_velocity.

    Args:
        diversity_map: optional dict[normalized_name -> (distinct_hashes, total)].
            If None, no penalty (single-listing fallback path skips this signal).
    """
    cfg = config.get('template_farm', {})
    if diversity_map is None:
        return 0, "No diversity data"

    name = _normalize_company_name(listing.company_name)
    entry = diversity_map.get(name)
    if not entry:
        return 0, "No diversity data"

    distinct, total = entry
    if total < cfg.get('min_listings', 5):
        return 0, f"Too few listings ({total}) to evaluate"

    ratio = distinct / total if total else 1.0
    threshold = cfg.get('explicit_penalty_threshold', 0.2)
    if ratio >= threshold:
        return 0, f"Diversity OK ({ratio:.0%})"

    penalty = cfg.get('explicit_penalty', -5)
    return penalty, f"Template farm: {distinct} unique of {total} listings ({ratio:.0%})"


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

    if not listing.date_last_seen:
        return 0, "No last-seen date"

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


# =============================================================================
# GENZJOBS-ENRICHED SIGNALS
# =============================================================================

def calculate_data_completeness(listing, config):
    """
    Calculate data completeness score based on rich listing data from genzjobs.
    Awards points for requirements, benefits, logo, website, skills.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config.get('data_completeness', {})
    if not cfg:
        return 0, "No data_completeness config"

    points = 0
    details = []

    if getattr(listing, 'has_requirements', False):
        points += cfg.get('has_requirements', 2)
        details.append("requirements")

    if getattr(listing, 'has_benefits', False):
        points += cfg.get('has_benefits', 2)
        details.append("benefits")

    if getattr(listing, 'has_company_logo', False):
        points += cfg.get('has_logo', 1)
        details.append("logo")

    if getattr(listing, 'has_company_website', False):
        points += cfg.get('has_website', 1)
        details.append("website")

    skills_count = getattr(listing, 'skills_count', 0) or 0
    min_skills = cfg.get('min_skills_count', 3)
    if skills_count >= min_skills:
        points += cfg.get('has_skills', 2)
        details.append(f"{skills_count} skills")

    points = min(points, cfg.get('max_points', 8))
    explanation = ", ".join(details) if details else "minimal data"

    return round(points, 1), explanation


def calculate_classification_confidence(listing, config):
    """
    Calculate bonus/penalty based on ML classification confidence.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config.get('classification_confidence', {})
    if not cfg:
        return 0, "No classification_confidence config"

    confidence = getattr(listing, 'classification_confidence', None)
    if confidence is None:
        return 0, "No classification data"

    high_threshold = cfg.get('high_threshold', 0.8)
    low_threshold = cfg.get('low_threshold', 0.3)

    if confidence >= high_threshold:
        points = cfg.get('max_points', 3)
        return points, f"High confidence ({confidence:.0%})"
    elif confidence <= low_threshold:
        points = cfg.get('min_points', -3)
        return points, f"Low confidence ({confidence:.0%})"

    return 0, f"Moderate confidence ({confidence:.0%})"


def calculate_publisher_trustworthiness(listing, config):
    """
    Calculate bonus for listings from trusted direct ATS sources or known publishers.

    Returns:
        tuple: (points, explanation)
    """
    cfg = config.get('publisher_trustworthiness', {})
    if not cfg:
        return 0, "No publisher_trustworthiness config"

    source = getattr(listing, 'source_ats', '') or ''
    publisher = getattr(listing, 'publisher', '') or ''

    direct_ats = cfg.get('direct_ats_sources', [])
    known_pubs = cfg.get('known_publishers', [])

    if source.lower() in direct_ats:
        points = cfg.get('direct_ats_bonus', 5)
        return points, f"Direct ATS ({source})"

    if publisher.lower() in known_pubs or source.lower() in known_pubs:
        points = cfg.get('known_publisher_bonus', 2)
        return points, f"Known publisher ({publisher or source})"

    return 0, f"Unknown publisher ({publisher or source})"
