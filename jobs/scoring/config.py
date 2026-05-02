"""
Hiring Activity Score (HAS) Configuration

Score configuration and weights for the HAS algorithm.
Override in settings.py via HAS_CONFIG dictionary.
"""

import copy
from django.conf import settings

# Default configuration - can be overridden in settings.py
DEFAULT_HAS_CONFIG = {
    # Base score - all listings start here
    'base_score': 40,

    # Publishing threshold - minimum score to auto-publish to board
    'publish_threshold': 65,

    # Score bands for categorization
    'score_bands': {
        'very_active': (80, 100),
        'likely_active': (65, 79),
        'uncertain': (50, 64),
        'low_signal': (0, 49),
    },

    # === POSITIVE SIGNALS ===

    # Freshness: Linear decay over time
    'freshness': {
        'max_points': 15,
        'decay_days': 60,  # Full decay over 60 days (matches job expiration period)
    },

    # Specificity: Salary, location, description quality
    'specificity': {
        'max_points': 10,
        'has_salary': 4,       # Has salary info
        'has_location': 2,     # Has specific location
        'description_quality': 4,  # Description length/quality
        'min_description_length': 500,  # Chars for full points
    },

    # Company Velocity: Volume of new listings in lookback window.
    # Computed inline from ScrapedJobListing aggregates by normalized company_name.
    # Tiers: list of (min_count, points) — first matching tier wins (descending order).
    'company_velocity': {
        'max_points': 10,
        'lookback_days': 30,
        'tiers': [
            (50, 10),
            (20, 8),
            (10, 6),
            (5, 4),
            (2, 2),
            (1, 1),
        ],
    },

    # ATS Behavior: Description updates, similar role closures
    'ats_behavior': {
        'max_points': 5,
        'description_updated': 3,    # Description changed recently
        'similar_role_closed': 2,    # Similar role was closed
    },

    # Company Reputation: Curated bonus for known reputable employers.
    # Sources (any match awards points):
    #   1. FeaturedEmployer directory entries (auto-loaded) → featured_employer_bonus
    #   2. `overrides` map below: keyed by lowercase normalized company_name → tier (1 or 2)
    'company_reputation': {
        'min_points': 0,
        'max_points': 8,
        'featured_employer_bonus': 8,
        'tier_1_bonus': 8,
        'tier_2_bonus': 4,
        # Names should match listing.company_name lowercased + stripped.
        # FeaturedEmployer entries are matched separately; only add names NOT in that
        # directory, or names you want to also score reputable when they appear under
        # a slightly different listing form.
        'overrides': {
            # Banking & financial services
            'capital one': 1,
            'visa': 1,
            'mastercard': 1,
            'wells fargo': 1,
            'american express': 1,
            'fidelity': 1,
            'fidelity investments': 1,
            'schwab': 1,
            'charles schwab': 1,
            'paypal': 1,
            'sofi': 1,
            'affirm': 1,
            'stripe': 1,
            'square': 1,
            'block': 1,
            'coinbase': 1,
            # Tech (big brands not already in FeaturedEmployer)
            'salesforce': 1,
            'oracle': 1,
            'ibm': 1,
            'cisco': 1,
            'intel': 1,
            'nvidia': 1,
            'adobe': 1,
            'workday': 1,
            'servicenow': 1,
            'snowflake': 1,
            'databricks': 1,
            'cloudflare': 1,
            'datadog': 1,
            'mongodb': 1,
            'hubspot': 1,
            'atlassian': 1,
            'shopify': 1,
            'airbnb': 1,
            'doordash': 1,
            'uber': 1,
            'lyft': 1,
            'spotify': 1,
            'pinterest': 1,
            'linkedin': 1,
            'openai': 1,
            'anthropic': 1,
            # Retail / consumer
            'walmart': 1,
            'target': 1,
            'costco': 1,
            'home depot': 1,
            "lowe's": 1,
            'best buy': 1,
            'starbucks': 1,
            'mcdonald\'s': 1,
            'mcdonalds': 1,
            'nike': 1,
            # Entertainment / media
            'disney': 1,
            'walt disney': 1,
            'walt disney company': 1,
            'warner bros. discovery': 1,
            'comcast': 1,
            'nbcuniversal': 1,
            # Healthcare / pharma
            'pfizer': 1,
            'johnson & johnson': 1,
            'merck': 1,
            'moderna': 1,
            'eli lilly': 1,
            'abbvie': 1,
            'unitedhealth group': 1,
            'cvs health': 1,
            # Aerospace / defense
            'raytheon': 1,
            'rtx': 1,
            'general dynamics': 1,
            # Auto / industrial
            'ford': 1,
            'general motors': 1,
            'gm': 1,
            'caterpillar': 1,
            'john deere': 1,
            'deere & company': 1,
            # Government (federal)
            'u.s. customs and border protection': 1,
            'us customs and border protection': 1,
            'internal revenue service': 1,
            'department of defense': 1,
            'nasa': 1,
        },
    },

    # Industry Adjustment
    'industry_adjustment': {
        'min_points': -5,
        'max_points': 10,
        # Slower-hiring industries (longer TTF = higher score for same age)
        'slow_industries': ['healthcare', 'government', 'education', 'legal'],
        'slow_bonus': 5,
        # Fast-hiring industries (if old, penalize more)
        'fast_industries': ['retail', 'food_service', 'hospitality', 'staffing'],
        'fast_penalty': -5,
    },

    # === NEGATIVE SIGNALS ===

    # Repost Penalty
    'repost_penalty': {
        'min_points': -15,
        'points_per_repost': -5,
    },

    # Evergreen Penalty: Open 90+ days unchanged
    'evergreen_penalty': {
        'min_points': -20,
        'threshold_days': 90,
        'no_change_multiplier': 1.5,  # Extra penalty if no description changes
    },

    # Boilerplate Penalty: High similarity across listings
    'boilerplate_penalty': {
        'min_points': -10,
        'high_ratio_threshold': 0.7,  # 70% similar content
    },

    # Stale Listing Penalty
    'stale_penalty': {
        'min_points': -10,
        'stale_threshold_days': 21,  # Days since last seen in a sync
    },

    # === GENZJOBS-ENRICHED SIGNALS ===

    # Data Completeness: points for rich listing data
    'data_completeness': {
        'max_points': 8,
        'has_requirements': 2,
        'has_benefits': 2,
        'has_logo': 1,
        'has_website': 1,
        'has_skills': 2,         # At least 3 skills
        'min_skills_count': 3,
    },

    # Classification Confidence: ML model confidence
    'classification_confidence': {
        'max_points': 3,
        'min_points': -3,
        'high_threshold': 0.8,   # Bonus above this
        'low_threshold': 0.3,    # Penalty below this
    },

    # Publisher Trustworthiness: bonus for direct ATS or known publishers
    'publisher_trustworthiness': {
        'max_points': 5,
        'direct_ats_bonus': 5,
        'known_publisher_bonus': 2,
        'direct_ats_sources': ['greenhouse', 'lever', 'ashby', 'smartrecruiters', 'workday', 'icims', 'bamboohr', 'jobvite', 'taleo'],
        'known_publishers': ['remotive', 'usajobs', 'arbeitnow', 'jobicy'],
    },

    # === CLAMPING ===
    'min_score': 0,
    'max_score': 100,
}


def get_config():
    """
    Get the HAS configuration, merging defaults with settings overrides.

    Returns:
        dict: The merged configuration dictionary
    """
    config = copy.deepcopy(DEFAULT_HAS_CONFIG)

    # Deep merge with settings override if present
    if hasattr(settings, 'HAS_CONFIG'):
        _deep_merge(config, settings.HAS_CONFIG)

    return config


def _deep_merge(base: dict, override: dict) -> None:
    """
    Deep merge override into base dictionary (in place).
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
