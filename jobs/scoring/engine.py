"""
Hiring Activity Score (HAS) Engine

Core scoring engine that combines all signals to produce a final score.
"""

from .config import get_config
from . import signals


class HASEngine:
    """
    Hiring Activity Score calculation engine.

    Usage:
        engine = HASEngine()
        score, breakdown = engine.calculate_score(listing)

        # Or with pre-loaded profile
        profile = listing.company.hiring_profile if listing.company else None
        score, breakdown = engine.calculate_score(listing, profile=profile)
    """

    VERSION = 3  # Bumped: inline velocity + curated reputation (2026-05-02)

    def __init__(self, config=None):
        """
        Initialize the engine with optional config override.

        Args:
            config: Optional config dict. If None, loads from settings/defaults.
        """
        self.config = config or get_config()
        self._velocity_map = None
        self._featured_set = None

    def prepare_caches(self):
        """
        Precompute caches for batch scoring so per-listing signal calls don't hit
        the DB. Builds:
          - velocity_map: {lower(company_name): new_listings_in_lookback_window}
          - featured_set: {lower(name) for name in FeaturedEmployer}

        Idempotent — call once before bulk_score / a sequence of score_listing calls.
        """
        from datetime import timedelta
        from django.db.models import Count
        from django.db.models.functions import Lower, Trim
        from django.utils import timezone
        from jobs.models import ScrapedJobListing

        lookback = self.config['company_velocity'].get('lookback_days', 30)
        cutoff = timezone.now() - timedelta(days=lookback)
        rows = (
            ScrapedJobListing.objects
            .filter(date_first_seen__gte=cutoff)
            .annotate(_norm=Lower(Trim('company_name')))
            .values('_norm')
            .annotate(count=Count('id'))
        )
        self._velocity_map = {r['_norm']: r['count'] for r in rows if r['_norm']}

        try:
            from directory.models import FeaturedEmployer
            self._featured_set = {
                (fe_name or '').lower().strip()
                for fe_name in FeaturedEmployer.objects.values_list('name', flat=True)
            }
            self._featured_set.discard('')
        except Exception:
            self._featured_set = set()

    def calculate_score(self, listing, profile=None):
        """
        Calculate the Hiring Activity Score for a listing.

        Args:
            listing: ScrapedJobListing instance
            profile: Optional CompanyHiringProfile instance

        Returns:
            tuple: (total_score, breakdown_dict)
                - total_score: int from 0-100
                - breakdown_dict: dict with individual signal contributions
        """
        # Get company hiring profile if not provided
        if profile is None and listing.company:
            from jobs.models import CompanyHiringProfile
            try:
                profile = listing.company.hiring_profile
            except CompanyHiringProfile.DoesNotExist:
                profile = None

        breakdown = {}

        # Start with base score
        total = self.config['base_score']
        breakdown['base'] = {
            'points': self.config['base_score'],
            'explanation': 'Base score'
        }

        # === POSITIVE SIGNALS ===

        # Freshness
        points, explanation = signals.calculate_freshness(listing, self.config)
        total += points
        breakdown['freshness'] = {'points': points, 'explanation': explanation}

        # Specificity
        points, explanation = signals.calculate_specificity(listing, self.config)
        total += points
        breakdown['specificity'] = {'points': points, 'explanation': explanation}

        # Company Velocity (inline; no profile required)
        points, explanation = signals.calculate_company_velocity(
            listing, self.config, velocity_map=self._velocity_map
        )
        total += points
        breakdown['company_velocity'] = {'points': points, 'explanation': explanation}

        # ATS Behavior
        points, explanation = signals.calculate_ats_behavior(listing, self.config)
        total += points
        breakdown['ats_behavior'] = {'points': points, 'explanation': explanation}

        # Company Reputation (curated: FeaturedEmployer + config overrides)
        points, explanation = signals.calculate_company_reputation(
            listing, self.config, featured_set=self._featured_set
        )
        total += points
        breakdown['company_reputation'] = {'points': points, 'explanation': explanation}

        # Industry Adjustment
        points, explanation = signals.calculate_industry_adjustment(
            listing, self.config, profile
        )
        total += points
        breakdown['industry_adjustment'] = {'points': points, 'explanation': explanation}

        # Data Completeness (genzjobs enriched)
        points, explanation = signals.calculate_data_completeness(listing, self.config)
        total += points
        breakdown['data_completeness'] = {'points': points, 'explanation': explanation}

        # Classification Confidence (genzjobs enriched)
        points, explanation = signals.calculate_classification_confidence(listing, self.config)
        total += points
        breakdown['classification_confidence'] = {'points': points, 'explanation': explanation}

        # Publisher Trustworthiness (genzjobs enriched)
        points, explanation = signals.calculate_publisher_trustworthiness(listing, self.config)
        total += points
        breakdown['publisher_trustworthiness'] = {'points': points, 'explanation': explanation}

        # === NEGATIVE SIGNALS ===

        # Repost Penalty
        points, explanation = signals.calculate_repost_penalty(listing, self.config)
        total += points
        breakdown['repost_penalty'] = {'points': points, 'explanation': explanation}

        # Evergreen Penalty
        points, explanation = signals.calculate_evergreen_penalty(listing, self.config)
        total += points
        breakdown['evergreen_penalty'] = {'points': points, 'explanation': explanation}

        # Boilerplate Penalty
        points, explanation = signals.calculate_boilerplate_penalty(
            listing, self.config, profile
        )
        total += points
        breakdown['boilerplate_penalty'] = {'points': points, 'explanation': explanation}

        # Stale Penalty
        points, explanation = signals.calculate_stale_penalty(listing, self.config)
        total += points
        breakdown['stale_penalty'] = {'points': points, 'explanation': explanation}

        # Clamp to valid range
        total = max(self.config['min_score'], min(self.config['max_score'], total))
        total = round(total)

        return total, breakdown

    def get_score_band(self, score):
        """
        Get the score band label for a given score.

        Args:
            score: int score value 0-100

        Returns:
            str: Score band key ('very_active', 'likely_active', etc.)
        """
        bands = self.config['score_bands']

        for band_name, (min_val, max_val) in bands.items():
            if min_val <= score <= max_val:
                return band_name

        return 'low_signal'  # Default fallback

    def should_publish(self, score):
        """
        Determine if a listing should be auto-published based on score.

        Args:
            score: int score value 0-100

        Returns:
            bool: True if score meets publish threshold
        """
        return score >= self.config['publish_threshold']

    def score_listing(self, listing, save=True):
        """
        Calculate score for a listing and optionally save to HiringActivityScore.

        Args:
            listing: ScrapedJobListing instance
            save: bool, whether to save the score to database

        Returns:
            HiringActivityScore instance (saved or unsaved)
        """
        from jobs.models import HiringActivityScore

        score, breakdown = self.calculate_score(listing)
        band = self.get_score_band(score)

        # Get or create the score record
        try:
            has_obj = listing.activity_score
            has_obj.total_score = score
            has_obj.score_band = band
            has_obj.score_breakdown = breakdown
            has_obj.score_version = self.VERSION
        except HiringActivityScore.DoesNotExist:
            has_obj = HiringActivityScore(
                listing=listing,
                total_score=score,
                score_band=band,
                score_breakdown=breakdown,
                score_version=self.VERSION
            )

        if save:
            has_obj.save()  # save() will sync published_to_board

        return has_obj

    def bulk_score(self, listings, batch_size=100):
        """
        Score multiple listings efficiently.

        Args:
            listings: QuerySet or list of ScrapedJobListing instances
            batch_size: int, number to process before yielding progress

        Yields:
            tuple: (processed_count, total_count, current_listing)
        """
        from jobs.models import HiringActivityScore

        total = listings.count() if hasattr(listings, 'count') else len(listings)
        processed = 0

        for listing in listings:
            self.score_listing(listing, save=True)
            processed += 1

            if processed % batch_size == 0:
                yield processed, total, listing

        # Final yield
        yield processed, total, None
