"""
Hiring Activity Score (HAS) Scoring Engine

This package provides the scoring system for evaluating scraped job listings
to determine if they represent active hiring opportunities vs ghost/evergreen postings.

Usage:
    from jobs.scoring import HASEngine

    engine = HASEngine()
    score, breakdown = engine.calculate_score(listing)
"""

from .engine import HASEngine
from .config import get_config

__all__ = ['HASEngine', 'get_config']
