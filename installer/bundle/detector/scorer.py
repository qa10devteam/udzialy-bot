"""Property share scorer - detects if a real estate listing is selling a co-ownership share.

This module implements a multi-signal scoring system that analyzes listing titles
and descriptions to determine if they represent property share (udział w nieruchomości)
sales rather than regular property sales.

Scoring breakdown:
- Title keywords match: up to +35 points
- Description pattern match: up to +25 points
- Fraction detected: +15 points
- Inheritance/legal context: up to +10 points
- Syndyk + udział combo boost: +20 points
- Price anomaly (unusually low): up to +8 points
- Negative penalties: -15 to -35 points each
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from detector.keywords import (
    COMPILED_HIGH,
    COMPILED_MEDIUM,
    COMPILED_LOW,
    COMPILED_NEGATIVE,
    COMPILED_FRACTIONS,
    COMPILED_INHERITANCE,
)

# Threshold for is_share classification (lowered from 50 to 25 for title-only scoring)
SHARE_THRESHOLD = 25


@dataclass
class ScoringResult:
    """Result of property share scoring analysis.

    Attributes:
        score: Confidence score 0-100 that this listing is a property share sale.
        matched_keywords: List of keyword/pattern strings that matched.
        fraction_detected: The ownership fraction found (e.g., '1/2') or None.
        is_share: Whether score >= threshold, indicating likely property share.
        reasons: Human-readable list of scoring reasons (for debugging/display).
    """

    score: int
    matched_keywords: List[str] = field(default_factory=list)
    fraction_detected: Optional[str] = None
    is_share: bool = False
    reasons: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure score is clamped to 0-100 and is_share is set correctly."""
        self.score = max(0, min(100, self.score))
        self.is_share = self.score >= SHARE_THRESHOLD


class PropertyShareScorer:
    """Scorer that analyzes real estate listings to detect property share sales.

    Handles Polish text with or without diacritics (OLX users often skip them).
    Uses multi-signal scoring: keywords, fractions, legal context, price anomaly.

    Example:
        >>> scorer = PropertyShareScorer()
        >>> result = scorer.score("Sprzedaż udziału 1/2 w mieszkaniu", "Spadek po babci...")
        >>> result.is_share
        True
        >>> result.score
        65
    """

    # Typical price per m² thresholds (PLN) - below these is anomalous
    # These are conservative national averages; real thresholds vary by city
    PRICE_ANOMALY_THRESHOLD_PER_M2: float = 3000.0  # PLN/m² - very low for Poland

    def __init__(self) -> None:
        """Initialize the scorer with pre-compiled keyword patterns."""
        pass  # Patterns are module-level compiled constants

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching: lowercase, normalize unicode.

        Does NOT strip diacritics - patterns already handle both variants.

        Args:
            text: Input text to normalize.

        Returns:
            Normalized lowercase text.
        """
        if not text:
            return ""
        # Normalize unicode (NFC form) and lowercase
        normalized = unicodedata.normalize("NFC", text.lower().strip())
        # Collapse multiple whitespace
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _check_patterns(
        self, text: str, patterns: list, label: str
    ) -> Tuple[List[str], List[str]]:
        """Check text against a list of compiled patterns.

        Args:
            text: Normalized text to search.
            patterns: List of compiled regex patterns.
            label: Label for reason messages.

        Returns:
            Tuple of (matched_keywords, reasons).
        """
        matched: List[str] = []
        reasons: List[str] = []

        for pattern in patterns:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                matched.append(matched_text)
                reasons.append(f"{label}: '{matched_text}'")

        return matched, reasons

    def _detect_fraction(self, text: str) -> Optional[str]:
        """Detect ownership fraction in text.

        Args:
            text: Text to search for fractions.

        Returns:
            The fraction string (e.g., '1/2') or None.
        """
        # Unicode fraction mapping for normalization in output
        unicode_fraction_map = {
            '½': '1/2', '¼': '1/4', '¾': '3/4',
            '⅓': '1/3', '⅔': '2/3', '⅕': '1/5', '⅛': '1/8',
        }

        for pattern in COMPILED_FRACTIONS:
            match = pattern.search(text)
            if match:
                fraction = match.group(0)
                # Normalize unicode fractions to slash form
                if fraction in unicode_fraction_map:
                    return unicode_fraction_map[fraction]
                # Clean up whitespace around slash
                fraction = re.sub(r"\s*/\s*", "/", fraction)
                return fraction
        return None

    def _check_price_anomaly(
        self, price: Optional[float], area: Optional[float]
    ) -> Tuple[int, List[str]]:
        """Check if price per m² is anomalously low (suggesting share, not whole property).

        Args:
            price: Listing price in PLN (or None).
            area: Property area in m² (or None).

        Returns:
            Tuple of (bonus_points, reasons).
        """
        if price is None or area is None:
            return 0, []

        if area <= 0:
            return 0, []

        price_per_m2 = price / area

        if price_per_m2 < self.PRICE_ANOMALY_THRESHOLD_PER_M2:
            reason = (
                f"Price anomaly: {price_per_m2:.0f} PLN/m² "
                f"(below {self.PRICE_ANOMALY_THRESHOLD_PER_M2:.0f} threshold)"
            )
            return 8, [reason]

        return 0, []

    def _calculate_negative_penalties(
        self, text: str
    ) -> Tuple[int, List[str]]:
        """Calculate penalty points for negative (false positive) indicators.

        Args:
            text: Combined normalized text to check.

        Returns:
            Tuple of (total_penalty as negative int, reasons).
        """
        total_penalty = 0
        reasons: List[str] = []

        # Specific penalties with different weights
        penalty_map = [
            (r"udzia[łl]\s+w\s+gruncie\s+pod\s+budynkiem", -35, "udział w gruncie pod budynkiem"),
            (r"udzia[łl]y\s+w\s+sp[óo][łl]ce", -30, "udziały w spółce"),
            (r"udzia[łl][óo]w\s+w\s+sp[óo][łl]ce", -30, "udziałów w spółce"),
            (r"udzia[łl]\s+w\s+sp[óo][łl]ce", -30, "udział w spółce"),
            (r"wk[łl]ad\s+w[łl]asny", -20, "wkład własny"),
            (r"udzia[łl]\s+w\s+drodze", -15, "udział w drodze"),
            (r"cz[ęe][śs]ci\s+wsp[óo]lne", -15, "części wspólne"),
        ]

        for pattern_str, penalty, label in penalty_map:
            pattern = re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
            if pattern.search(text):
                total_penalty += penalty
                reasons.append(f"Negative: '{label}' ({penalty})")

        return total_penalty, reasons

    def _check_syndyk_boost(self, text: str) -> Tuple[int, List[str]]:
        """Check for syndyk + udział combination which is a very strong signal.

        Args:
            text: Combined normalized text.

        Returns:
            Tuple of (bonus_points, reasons).
        """
        has_syndyk = bool(re.search(r"syndyk", text, re.IGNORECASE))
        has_udzial = bool(re.search(r"udzia[łl]", text, re.IGNORECASE))

        if has_syndyk and has_udzial:
            return 20, ["Syndyk + udział combo boost: +20"]
        return 0, []

    def score(
        self,
        title: str,
        description: str,
        price: Optional[float] = None,
        area: Optional[float] = None,
    ) -> ScoringResult:
        """Score a listing to determine if it's selling a property share.

        Args:
            title: Listing title text.
            description: Listing description/body text.
            price: Optional listing price in PLN.
            area: Optional property area in m².

        Returns:
            ScoringResult with score, matched keywords, and reasoning.
        """
        # Normalize inputs
        norm_title = self._normalize_text(title or "")
        norm_desc = self._normalize_text(description or "")
        combined = f"{norm_title} {norm_desc}"

        total_score = 0
        all_matched: List[str] = []
        all_reasons: List[str] = []

        # --- TITLE KEYWORDS (up to +35) ---
        title_score = 0
        high_matched, high_reasons = self._check_patterns(
            norm_title, COMPILED_HIGH, "Title HIGH"
        )
        if high_matched:
            title_score = 35
            all_matched.extend(high_matched)
            all_reasons.extend(high_reasons)
        else:
            med_matched, med_reasons = self._check_patterns(
                norm_title, COMPILED_MEDIUM, "Title MEDIUM"
            )
            if med_matched:
                title_score = 25
                all_matched.extend(med_matched)
                all_reasons.extend(med_reasons)
            else:
                low_matched, low_reasons = self._check_patterns(
                    norm_title, COMPILED_LOW, "Title LOW"
                )
                if low_matched:
                    title_score = 10
                    all_matched.extend(low_matched)
                    all_reasons.extend(low_reasons)

        total_score += title_score
        if title_score > 0:
            all_reasons.append(f"Title keywords: +{title_score}")

        # --- DESCRIPTION PATTERNS (up to +25) ---
        desc_score = 0
        high_matched_d, high_reasons_d = self._check_patterns(
            norm_desc, COMPILED_HIGH, "Desc HIGH"
        )
        if high_matched_d:
            desc_score = 25
            all_matched.extend(high_matched_d)
            all_reasons.extend(high_reasons_d)
        else:
            med_matched_d, med_reasons_d = self._check_patterns(
                norm_desc, COMPILED_MEDIUM, "Desc MEDIUM"
            )
            if med_matched_d:
                desc_score = 18
                all_matched.extend(med_matched_d)
                all_reasons.extend(med_reasons_d)
            else:
                low_matched_d, low_reasons_d = self._check_patterns(
                    norm_desc, COMPILED_LOW, "Desc LOW"
                )
                if low_matched_d:
                    desc_score = 8
                    all_matched.extend(low_matched_d)
                    all_reasons.extend(low_reasons_d)

        total_score += desc_score
        if desc_score > 0:
            all_reasons.append(f"Description patterns: +{desc_score}")

        # --- FRACTION DETECTED (+15) ---
        fraction = self._detect_fraction(combined)
        if fraction:
            total_score += 15
            all_matched.append(fraction)
            all_reasons.append(f"Fraction detected: '{fraction}' (+15)")

        # --- INHERITANCE/LEGAL CONTEXT (up to +10) ---
        inherit_matched, inherit_reasons = self._check_patterns(
            combined, COMPILED_INHERITANCE, "Inheritance"
        )
        if inherit_matched:
            # Cap at +10, scale by number of matches
            inherit_score = min(10, len(inherit_matched) * 3)
            total_score += inherit_score
            all_matched.extend(inherit_matched)
            all_reasons.extend(inherit_reasons)
            all_reasons.append(f"Inheritance context: +{inherit_score}")

        # --- SYNDYK + UDZIAŁ COMBO BOOST (+20) ---
        syndyk_bonus, syndyk_reasons = self._check_syndyk_boost(combined)
        total_score += syndyk_bonus
        all_reasons.extend(syndyk_reasons)

        # --- PRICE ANOMALY (up to +8) ---
        price_bonus, price_reasons = self._check_price_anomaly(price, area)
        total_score += price_bonus
        all_reasons.extend(price_reasons)

        # --- NEGATIVE PENALTIES ---
        penalties, penalty_reasons = self._calculate_negative_penalties(combined)
        total_score += penalties  # penalties are negative
        all_reasons.extend(penalty_reasons)

        # Build result
        result = ScoringResult(
            score=total_score,
            matched_keywords=all_matched,
            fraction_detected=fraction,
            reasons=all_reasons,
        )

        return result
