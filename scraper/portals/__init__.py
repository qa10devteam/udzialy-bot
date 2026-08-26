"""Portal scrapers package."""

from scraper.portals.morizon import MorizonScraper
from scraper.portals.gratka import GratkaScraper
from scraper.portals.domiporta import DomiportaScraper
from scraper.portals.olx import OlxScraper
from scraper.portals.otodom import OtodomScraper
from scraper.portals.nieruchomosci_online import NieruchomosciOnlineScraper
from scraper.portals.allegro import AllegroScraper

ALL_SCRAPERS = [
    MorizonScraper,
    GratkaScraper,
    DomiportaScraper,
    OlxScraper,
    OtodomScraper,
    NieruchomosciOnlineScraper,
    AllegroScraper,
]

__all__ = [
    "MorizonScraper",
    "GratkaScraper",
    "DomiportaScraper",
    "OlxScraper",
    "OtodomScraper",
    "NieruchomosciOnlineScraper",
    "AllegroScraper",
    "ALL_SCRAPERS",
]
