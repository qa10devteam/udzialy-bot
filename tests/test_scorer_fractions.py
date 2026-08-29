"""Fraction detection must not mistake area/price/date numbers for ownership shares."""

import pytest

from detector.scorer import PropertyShareScorer


@pytest.fixture
def scorer():
    return PropertyShareScorer()


@pytest.mark.parametrize("text,expected", [
    ("Sprzedam udział 1/2 w mieszkaniu", "1/2"),
    ("udział w wysokości 14/40 w lokalu", "14/40"),
    ("udziały 12/20 w nieruchomości", "12/20"),
    ("Udział 190/2 w działce rolnej 250 m²", None),   # 190/2 is not a share
    ("udział w nieruchomości 759/21 Gdańsk", None),    # improper fraction
    ("udział 1/2024 w budynku", None),                 # a year, not a share
    ("½ udziału w domu", "1/2"),
    ("udział 3/4 w kamienicy", "3/4"),
    ("Mieszkanie 45 m2, 2/3 piętro udział 1/8", "1/8"),  # specific patterns (1/8) take priority over 2/3
])
def test_fraction_plausibility(scorer, text, expected):
    assert scorer.score(text, "").fraction_detected == expected


def test_implausible_fraction_does_not_get_fraction_bonus(scorer):
    with_bad = scorer.score("Udział 190/2 w działce rolnej", "")
    with_good = scorer.score("Udział 1/2 w działce rolnej", "")
    assert with_good.score - with_bad.score == 15
