"""Tests for PropertyShareScorer - detection of property share listings.

Tests cover:
- True positives (listings that ARE property shares)
- True negatives (listings that are NOT property shares)
- Edge cases (ambiguous text, missing diacritics, mixed signals)
- Score ranges and thresholds
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from detector.scorer import PropertyShareScorer, ScoringResult


class TestTruePositives:
    """Test cases that SHOULD be detected as property shares (score >= 50)."""

    def test_clear_share_sale_in_title(self, scorer: PropertyShareScorer) -> None:
        """Title explicitly mentions share sale."""
        result = scorer.score(
            title="Sprzedaż udziału 1/2 w mieszkaniu 3-pokojowym",
            description="Oferuję do sprzedaży udział w mieszkaniu.",
        )
        assert result.is_share is True
        assert result.score >= 60
        assert result.fraction_detected == "1/2"
        assert len(result.matched_keywords) > 0

    def test_inheritance_share(self, scorer: PropertyShareScorer) -> None:
        """Typical inheritance scenario with share sale."""
        result = scorer.score(
            title="Udział w mieszkaniu po spadku",
            description=(
                "Sprzedam udział 1/4 w mieszkaniu odziedziczonym po babci. "
                "Postępowanie spadkowe zakończone, akt notarialny gotowy. "
                "Księga wieczysta KW WA1M/00345678/9."
            ),
        )
        assert result.is_share is True
        assert result.score >= 65
        assert "1/4" in (result.fraction_detected or "")

    def test_fraction_in_description_only(self, scorer: PropertyShareScorer) -> None:
        """Fraction appears only in description."""
        result = scorer.score(
            title="Współwłasność sprzedaż - mój udział",
            description="Mój udział wynosi 1/3 całości nieruchomości. Spadek po rodzicach.",
        )
        assert result.is_share is True
        assert result.fraction_detected == "1/3"

    def test_kamienica_share(self, scorer: PropertyShareScorer) -> None:
        """Share in a tenement house (kamienica)."""
        result = scorer.score(
            title="Udział w kamienicy - centrum miasta",
            description=(
                "Sprzedam udział 2/3 w zabytkowej kamienicy. "
                "Współwłasność po rozwodzie, podział majątku."
            ),
        )
        assert result.is_share is True
        assert result.score >= 55

    def test_low_price_anomaly_boosts_score(self, scorer: PropertyShareScorer) -> None:
        """Abnormally low price per m² suggests it's a share, not whole property."""
        result = scorer.score(
            title="Udział w mieszkaniu Gdynia",
            description="Sprzedam swój udział w nieruchomości.",
            price=45000.0,
            area=60.0,  # 750 PLN/m² - way below market
        )
        assert result.is_share is True
        # Price anomaly should add points
        assert any("anomaly" in r.lower() for r in result.reasons)


class TestTrueNegatives:
    """Test cases that should NOT be detected as property shares (score < 50)."""

    def test_regular_apartment_sale(self, scorer: PropertyShareScorer) -> None:
        """Normal apartment listing with no share indicators."""
        result = scorer.score(
            title="Mieszkanie 3-pokojowe, 65m2, Gdynia Orłowo",
            description=(
                "Sprzedam mieszkanie w doskonałej lokalizacji. "
                "3 pokoje, kuchnia, łazienka. Piętro 3/5."
            ),
        )
        assert result.is_share is False
        assert result.score < 30

    def test_udzial_w_gruncie_pod_budynkiem(self, scorer: PropertyShareScorer) -> None:
        """'Udział w gruncie pod budynkiem' is standard for apartments - NOT a share sale."""
        result = scorer.score(
            title="Mieszkanie 50m2 z garażem",
            description=(
                "Do mieszkania przynależy udział w gruncie pod budynkiem "
                "oraz udział w częściach wspólnych nieruchomości. "
                "Cena 350 000 PLN."
            ),
        )
        assert result.is_share is False
        assert result.score < 50

    def test_wklad_wlasny(self, scorer: PropertyShareScorer) -> None:
        """'Wkład własny' (down payment) - financial term, not share sale."""
        result = scorer.score(
            title="Mieszkanie idealne jako wkład własny",
            description=(
                "Świetna inwestycja. Możliwość wykorzystania jako wkład własny "
                "do kredytu hipotecznego."
            ),
        )
        assert result.is_share is False

    def test_udzialy_w_spolce(self, scorer: PropertyShareScorer) -> None:
        """'Udziały w spółce' - company shares, not property shares."""
        result = scorer.score(
            title="Sprzedaż udziałów w spółce z nieruchomościami",
            description=(
                "Sprzedam 100% udziałów w spółce z o.o. posiadającej "
                "nieruchomość komercyjną."
            ),
        )
        assert result.is_share is False

    def test_udzial_w_drodze(self, scorer: PropertyShareScorer) -> None:
        """'Udział w drodze' is standard for plots - not a share sale."""
        result = scorer.score(
            title="Działka budowlana 800m2",
            description=(
                "Sprzedam działkę budowlaną. W cenie udział w drodze dojazdowej "
                "1/8. Media na granicy działki."
            ),
        )
        # Should be penalized heavily
        assert result.score < 50


class TestEdgeCases:
    """Edge cases and special scenarios."""

    def test_missing_diacritics_olx_style(self, scorer: PropertyShareScorer) -> None:
        """OLX users often skip Polish diacritics - should still detect."""
        result = scorer.score(
            title="Sprzedaz udzialu 1/2 w mieszkaniu",
            description="Sprzedam udzial w nieruchomosci po spadku.",
        )
        assert result.is_share is True
        assert result.score >= 50

    def test_empty_description(self, scorer: PropertyShareScorer) -> None:
        """Handle listings with empty/missing description gracefully."""
        result = scorer.score(
            title="Udział 1/2 w mieszkaniu",
            description="",
        )
        assert result.is_share is True  # Title alone should be enough
        assert result.fraction_detected == "1/2"

    def test_none_description(self, scorer: PropertyShareScorer) -> None:
        """Handle None description."""
        result = scorer.score(
            title="Sprzedaż udziału 1/2 w nieruchomości",
            description=None,
        )
        assert result.is_share is True

    def test_empty_title_and_description(self, scorer: PropertyShareScorer) -> None:
        """Handle completely empty inputs."""
        result = scorer.score(title="", description="")
        assert result.is_share is False
        assert result.score == 0

    def test_score_never_exceeds_100(self, scorer: PropertyShareScorer) -> None:
        """Score should be clamped to max 100."""
        result = scorer.score(
            title="Sprzedaż udziału 1/2 w mieszkaniu spadek",
            description=(
                "Sprzedam udział 1/2 w mieszkaniu po spadku. "
                "Postępowanie spadkowe zakończone. Akt notarialny. "
                "Księga wieczysta. Sąd rejonowy potwierdził. "
                "Współwłasność sprzedaż. Testament."
            ),
            price=20000.0,
            area=80.0,
        )
        assert result.score <= 100

    def test_score_never_below_zero(self, scorer: PropertyShareScorer) -> None:
        """Score should be clamped to minimum 0."""
        result = scorer.score(
            title="Mieszkanie z udziałem w gruncie pod budynkiem",
            description=(
                "Udział w częściach wspólnych nieruchomości. "
                "Wkład własny nie wymagany. Udziały w spółce osobno."
            ),
        )
        assert result.score >= 0

    def test_mixed_signals(self, scorer: PropertyShareScorer) -> None:
        """Listing with both positive and negative signals."""
        result = scorer.score(
            title="Udział 1/4 w nieruchomości z drogą",
            description=(
                "Sprzedam udział 1/4 w domu jednorodzinnym. "
                "W cenie udział w drodze dojazdowej 1/8."
            ),
        )
        # Should still detect as share despite road mention
        # because the primary signal is strong
        assert result.score >= 30  # Penalized but not zeroed

    def test_scoring_result_dataclass(self, scorer: PropertyShareScorer) -> None:
        """Verify ScoringResult has all expected fields."""
        result = scorer.score(title="Test", description="Test")
        assert hasattr(result, "score")
        assert hasattr(result, "matched_keywords")
        assert hasattr(result, "fraction_detected")
        assert hasattr(result, "is_share")
        assert hasattr(result, "reasons")
        assert isinstance(result.matched_keywords, list)
        assert isinstance(result.reasons, list)
