"""
Industry weight profiles for the HAS scoring engine.

Each profile is a partial config dict that is deep-merged onto DEFAULT_HAS_CONFIG.
The engine resolves a profile by the listing's `industry_category` (synced from
genzjobs `CompanyATS.industryCategory` via sync_genzjobs). Null/unknown industry
falls back to the default profile (no overrides).

Profile keys match the genzjobs `IndustryCategory` enum values verbatim:
TECHNOLOGY, FINANCE_AND_BANKING, HEALTHCARE, CONSULTING, AEROSPACE_AND_DEFENSE,
GOVERNMENT, RETAIL_AND_ECOMMERCE, MEDIA_AND_ENTERTAINMENT, OTHER.

To add a new industry profile, append an entry to PROFILES and bump
PROFILE_VERSION. The engine records the active profile + version on each
HiringActivityScore so tuning iterations can be compared.
"""

# Bump when any profile content changes (added industries, changed overrides).
# Recorded on HiringActivityScore.weight_profile_version.
PROFILE_VERSION = 1

DEFAULT_PROFILE_KEY = 'default'


PROFILES = {
    # Default: no overrides. DEFAULT_HAS_CONFIG applies as-is.
    DEFAULT_PROFILE_KEY: {},

    # Tech roles tend to ghost faster: tighter freshness window, harder repost
    # penalty, higher reward for salary transparency, and explicit credit for
    # naming a stack.
    'TECHNOLOGY': {
        'freshness': {
            # Flat at max_points for first 14 days, linear decay to 0 by day 45.
            'decay_start_day': 14,
            'decay_days': 45,
            # Metadata baseline for future industry-calibration use.
            'expected_ttf_days': 30,
        },
        'repost_penalty': {
            # Multiplies per-repost penalty and floor (default -5/repost, floor -15).
            'penalty_multiplier': 1.5,
        },
        'specificity': {
            # +50% bonus for disclosed salary (default 4 -> 6).
            'has_salary': 6,
            # New sub-signal: credit listings that name a real stack.
            'tools_stack': 3,
            'min_tools_count': 5,
            # Bump cap so the new sub-signal can land.
            'max_points': 13,
        },
    },
}


def _normalize_industry(industry_category):
    """Normalize an industry string for PROFILES lookup. Returns None if blank."""
    if not industry_category:
        return None
    return str(industry_category).strip().upper()


def resolve_profile(industry_category):
    """
    Resolve a profile for a given industry.

    Args:
        industry_category: str or None. Typically the genzjobs IndustryCategory
            enum value (e.g. 'TECHNOLOGY'). Case-insensitive; None or unknown
            values resolve to the default profile.

    Returns:
        tuple: (profile_key, overrides_dict, profile_version)
            - profile_key: str — 'default' or the matched industry key
            - overrides_dict: dict — partial config to deep-merge over defaults
            - profile_version: int — PROFILE_VERSION at time of resolution
    """
    key = _normalize_industry(industry_category)
    if key and key in PROFILES:
        return key, PROFILES[key], PROFILE_VERSION
    return DEFAULT_PROFILE_KEY, PROFILES[DEFAULT_PROFILE_KEY], PROFILE_VERSION
