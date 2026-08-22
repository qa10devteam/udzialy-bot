"""Detector package - property share (udział w nieruchomości) detection and scoring."""

from detector.scorer import PropertyShareScorer, ScoringResult
from detector.keywords import (
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
    LOW_CONFIDENCE,
    NEGATIVE,
    FRACTION_PATTERNS,
    SEARCH_QUERIES,
)
from detector.filters import filter_by_score, filter_by_location, filter_by_price

__all__ = [
    "PropertyShareScorer",
    "ScoringResult",
    "HIGH_CONFIDENCE",
    "MEDIUM_CONFIDENCE",
    "LOW_CONFIDENCE",
    "NEGATIVE",
    "FRACTION_PATTERNS",
    "SEARCH_QUERIES",
    "filter_by_score",
    "filter_by_location",
    "filter_by_price",
]
