"""
Trojmiasto.pl scraper - STUB (blocked from datacenter IPs).

Trojmiasto.pl uses Cloudflare Turnstile which cannot be bypassed
from datacenter IPs. Requires residential IP or captcha-solving service.
This stub returns an empty list with a warning.
"""

import logging
from typing import Any, Dict, List, Optional

from scraper.base import BaseScraper, RawListing

logger = logging.getLogger(__name__)


class TrojmiastoScraper(BaseScraper):
    """Trojmiasto.pl scraper stub — blocked from datacenter IPs."""

    def __init__(self, **kwargs):
        super().__init__(stealth_layer=6, **kwargs)

    def get_portal_name(self) -> str:
        return "Trojmiasto"

    async def search(
        self, keywords: List[str], filters: Optional[Dict[str, Any]] = None
    ) -> List[dict]:
        """Return empty list — CF Turnstile blocks from datacenter IPs."""
        logger.warning(
            "Trojmiasto: CF Turnstile blocks from datacenter IPs, "
            "requires residential IP"
        )
        return []

    def parse_listing(self, html: str) -> Optional[RawListing]:
        """Not implemented — portal is blocked."""
        return None
