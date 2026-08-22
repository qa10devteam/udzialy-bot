"""Keyword and regex pattern lists for property share detection.

Polish real estate context:
- 'udział w nieruchomości' = co-ownership share in real property
- Fractions like 1/2, 1/4 indicate share size
- Must handle missing diacritics (OLX users often skip them)
"""

import re
from typing import List, Pattern

# --- HIGH CONFIDENCE keywords (strong indicators of share sale) ---
# These almost always mean a property share is being sold
HIGH_CONFIDENCE: List[str] = [
    r"sprzeda[żz] udzia[łl]u",
    r"sprzeda[żz] udzia[łl]",
    r"udzia[łl]\s+\d+\s*/\s*\d+",
    r"wsp[óo][łl]w[łl]asno[śs][ćc]\s+sprzeda",
    r"sprzedam\s+udzia[łl]",
    r"udzia[łl]\s+w\s+mieszkaniu",
    r"udzia[łl]\s+w\s+domu",
    r"udzia[łl]\s+w\s+lokalu",
    r"udzia[łl]\s+w\s+kamienicy",
    r"sprzeda[żz]\s+cz[ęe][śs]ci\s+nieruchomo[śs]ci",
    r"udzia[łl]\s+w\s+prawie\s+w[łl]asno[śs]ci",
]

# --- MEDIUM CONFIDENCE keywords ---
# Likely indicate share sale but need additional context
MEDIUM_CONFIDENCE: List[str] = [
    r"udzia[łl]\s+w\s+nieruchomo[śs]ci",
    r"cz[ęe][śs][ćc]\s+nieruchomo[śs]ci",
    r"u[łl]amek",
    r"u[łl]amkow[aey]\s+cz[ęe][śs][ćc]",
    r"wsp[óo][łl]w[łl]a[śs]ciciel",
    r"wsp[óo][łl]w[łl]asno[śs][ćc]",
    r"zniesienie\s+wsp[óo][łl]w[łl]asno[śs]ci",
    r"dzia[łl]\s+spadkow[yae]",
    r"udzia[łl]\s+spadkow[yae]",
    r"udzia[łl]y\s+w\s+nieruchomo[śs]ci",
]

# --- LOW CONFIDENCE keywords ---
# May indicate share sale but very ambiguous alone
LOW_CONFIDENCE: List[str] = [
    r"udzia[łl]",
    r"wsp[óo][łl]w[łl]asno[śs][ćc]",
    r"spadek",
    r"spadkobierc[aóo]w",
    r"cz[ęe][śs][ćc]\s+dzia[łl]ki",
    r"podzia[łl]\s+maj[ąa]tku",
]

# --- NEGATIVE keywords (false positive indicators) ---
# These patterns indicate the listing is NOT about selling a property share
NEGATIVE: List[str] = [
    r"udzia[łl]\s+w\s+gruncie\s+pod\s+budynkiem",
    r"udzia[łl]\s+w\s+gruncie",
    r"wk[łl]ad\s+w[łl]asny",
    r"udzia[łl]y\s+w\s+sp[óo][łl]ce",
    r"udzia[łl]\s+w\s+sp[óo][łl]ce",
    r"cz[ęe][śs]ci\s+wsp[óo]lne\s+nieruchomo[śs]ci",
    r"cz[ęe][śs]ci\s+wsp[óo]lne",
    r"udzia[łl]\s+w\s+drodze",
    r"udzia[łl]\s+w\s+drodze\s+dojazdowej",
    r"udzia[łl]\s+w\s+cz[ęe][śs]ciach\s+wsp[óo]lnych",
    r"udzia[łl]\s+w\s+nieruchomo[śs]ci\s+wsp[óo]lnej",
    r"udzia[łl]\s+w\s+gara[żz]u",
]

# --- FRACTION PATTERNS ---
# Regex patterns to detect ownership fractions in text
FRACTION_PATTERNS: List[str] = [
    r"\b1\s*/\s*2\b",
    r"\b1\s*/\s*3\b",
    r"\b1\s*/\s*4\b",
    r"\b1\s*/\s*5\b",
    r"\b1\s*/\s*6\b",
    r"\b1\s*/\s*8\b",
    r"\b1\s*/\s*10\b",
    r"\b1\s*/\s*12\b",
    r"\b1\s*/\s*16\b",
    r"\b2\s*/\s*3\b",
    r"\b3\s*/\s*4\b",
    r"\b3\s*/\s*8\b",
    r"\b5\s*/\s*8\b",
    r"\b7\s*/\s*8\b",
    r"\b\d{1,3}\s*/\s*\d{1,4}\b",  # General fraction pattern
]

# --- INHERITANCE/LEGAL CONTEXT ---
# Keywords that add context suggesting share ownership (not scored alone)
INHERITANCE_CONTEXT: List[str] = [
    r"spadek",
    r"spadkobierc[aóo]w",
    r"spadkow[yae]",
    r"dzia[łl]\s+spadku",
    r"post[ęe]powanie\s+spadkowe",
    r"testament",
    r"zachowek",
    r"ksi[ęe]ga\s+wieczysta",
    r"kw\s+[a-z]{2}\d+",
    r"s[ąa]d\s+rejonowy",
    r"akt\s+notarialny",
    r"notariusz",
    r"podzia[łl]\s+maj[ąa]tku",
    r"rozw[óo]d",
]

# --- SEARCH QUERIES ---
# Queries to use in real estate portal search boxes (OLX, Otodom, etc.)
SEARCH_QUERIES: List[str] = [
    "sprzedaż udziału w nieruchomości",
    "udział w mieszkaniu sprzedaż",
    "udział w nieruchomości",
    "współwłasność sprzedaż",
    "sprzedam udział",
    "udział 1/2 mieszkanie",
    "udział spadkowy nieruchomość",
    "część nieruchomości sprzedaż",
    "udział w domu",
    "udział w kamienicy",
    "zniesienie współwłasności sprzedaż",
    "ułamkowa część nieruchomości",
]


def compile_patterns(patterns: List[str]) -> List[Pattern]:
    """Compile a list of regex pattern strings into compiled Pattern objects.

    Args:
        patterns: List of regex pattern strings.

    Returns:
        List of compiled regex patterns (case-insensitive, Unicode).
    """
    return [re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns]


# Pre-compiled patterns for performance
COMPILED_HIGH = compile_patterns(HIGH_CONFIDENCE)
COMPILED_MEDIUM = compile_patterns(MEDIUM_CONFIDENCE)
COMPILED_LOW = compile_patterns(LOW_CONFIDENCE)
COMPILED_NEGATIVE = compile_patterns(NEGATIVE)
COMPILED_FRACTIONS = compile_patterns(FRACTION_PATTERNS)
COMPILED_INHERITANCE = compile_patterns(INHERITANCE_CONTEXT)
