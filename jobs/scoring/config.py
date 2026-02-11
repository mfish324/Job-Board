"""
Hiring Activity Score (HAS) Configuration

Score configuration and weights for the HAS algorithm.
Override in settings.py via HAS_CONFIG dictionary.
"""

from django.conf import settings

# Default configuration - can be overridden in settings.py
DEFAULT_HAS_CONFIG = {
    # Base score - all listings start here
    'base_score': 50,

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
        'decay_days': 30,  # Full decay over 30 days
    },

    # Specificity: Salary, location, description quality
    'specificity': {
        'max_points': 10,
        'has_salary': 4,       # Has salary info
        'has_location': 2,     # Has specific location
        'description_quality': 4,  # Description length/quality
        'min_description_length': 500,  # Chars for full points
    },

    # Company Velocity: Net positive job movement
    'company_velocity': {
        'max_points': 10,
        'positive_per_job': 2,  # Points per net new job in 30d
    },

    # ATS Behavior: Description updates, similar role closures
    'ats_behavior': {
        'max_points': 5,
        'description_updated': 3,    # Description changed recently
        'similar_role_closed': 2,    # Similar role was closed
    },

    # Company Reputation: From CompanyHiringProfile
    'company_reputation': {
        'min_points': -5,
        'max_points': 7,
        'good_reputation_threshold': 70,  # Profile score
        'bad_reputation_threshold': 30,
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
        'stale_threshold_days': 14,  # Days since last seen
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
    config = DEFAULT_HAS_CONFIG.copy()

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
