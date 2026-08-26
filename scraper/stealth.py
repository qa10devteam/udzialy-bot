"""
8-Layer Stealth Fetch Engine adapted from BeHive drones.

Escalation order:
  Layer 1: httpx with Chrome headers
  Layer 2: UA rotation (pool of 8+ real Chrome/Firefox UAs)
  Layer 3: curl_cffi TLS impersonation (chrome131 target)
  Layer 4: primp Rust TLS (chrome_131 target)
  Layer 5: nodriver headless CDP
  Layer 6: patchright stealth Playwright
  Layer 7: Jina relay (r.jina.ai)
  Layer 8: skip/report
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from scraper.utils.headers import get_chrome_headers, get_random_ua

logger = logging.getLogger(__name__)

# Block detection patterns
BLOCK_PATTERNS = [
    "just a moment",
    "access denied",
    "captcha",
    "verify you are human",
    "challenge-platform",
    "cf-browser-verification",
    "ray id",
    "attention required",
    "enable javascript",
    "please turn javascript on",
    "checking your browser",
    "bot detection",
    "blocked",
    "too many requests",
    "rate limit",
]

BLOCKED_STATUS_CODES = {403, 429, 503, 520, 521, 522, 523, 524}


def _is_blocked(html: str, status_code: int = 200) -> bool:
    """Detect if response indicates blocking/captcha."""
    if status_code in BLOCKED_STATUS_CODES:
        return True
    if not html:
        return True
    html_lower = html.lower()

    # Hard block indicators — flag regardless of page length
    # Only match when it's clearly a block PAGE (in title), not a passive JS snippet
    if "<title>just a moment</title>" in html_lower:
        return True
    if "verify you are human" in html_lower and len(html) < 50000:
        return True

    for pattern in BLOCK_PATTERNS:
        if pattern in html_lower:
            # Only flag if page is suspiciously short (real block page)
            if len(html) < 15000:
                return True
    return False


async def _layer1_httpx(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 1: httpx with Chrome headers."""
    try:
        import httpx
    except ImportError:
        logger.warning("Layer 1: httpx not available")
        return None
    
    headers = get_chrome_headers()
    transport_kwargs: Dict[str, Any] = {}
    
    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=timeout,
        proxy=proxy,
        verify=True,
        http2=True,
    ) as client:
        response = await client.get(url)
        if _is_blocked(response.text, response.status_code):
            logger.info(f"Layer 1 blocked for {url} (status={response.status_code})")
            return None
        return response.text


async def _layer2_ua_rotation(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 2: UA rotation with different header profiles."""
    try:
        import httpx
    except ImportError:
        logger.warning("Layer 2: httpx not available")
        return None
    
    # Try multiple UAs
    for _ in range(3):
        ua = get_random_ua()
        headers = get_chrome_headers(ua)
        
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=timeout,
            proxy=proxy,
            verify=True,
            http2=True,
        ) as client:
            response = await client.get(url)
            if not _is_blocked(response.text, response.status_code):
                return response.text
        
        await asyncio.sleep(1.0)
    
    logger.info(f"Layer 2 exhausted UA rotation for {url}")
    return None


async def _layer3_curl_cffi(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 3: curl_cffi TLS impersonation (chrome131 target)."""
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError:
        logger.warning("Layer 3: curl_cffi not available")
        return None
    
    try:
        async with AsyncSession(impersonate="chrome131") as session:
            proxies = {"https": proxy, "http": proxy} if proxy else None
            response = await session.get(
                url,
                proxies=proxies,
                timeout=timeout,
                allow_redirects=True,
            )
            if _is_blocked(response.text, response.status_code):
                logger.info(f"Layer 3 blocked for {url} (status={response.status_code})")
                return None
            # Cap response to 5MB to prevent memory issues
            text = response.text
            if len(text) > 5_000_000:
                text = text[:5_000_000]
            return text
    except Exception as e:
        logger.warning(f"Layer 3 error for {url}: {e}")
        return None


async def _layer4_primp(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 4: primp Rust TLS (chrome_131 target)."""
    try:
        import primp
    except ImportError:
        logger.warning("Layer 4: primp not available")
        return None
    
    try:
        # primp is sync, run in executor
        loop = asyncio.get_event_loop()
        
        def _fetch():
            client = primp.Client(
                impersonate="chrome_131",
                timeout=timeout,
                follow_redirects=True,
            )
            return client.get(url)
        
        response = await loop.run_in_executor(None, _fetch)
        if _is_blocked(response.text, response.status_code):
            logger.info(f"Layer 4 blocked for {url} (status={response.status_code})")
            return None
        return response.text
    except Exception as e:
        logger.warning(f"Layer 4 error for {url}: {e}")
        return None


async def _layer5_nodriver(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 5: nodriver headless CDP (bypasses CF Bot Management)."""
    try:
        import nodriver as uc
    except ImportError:
        logger.warning("Layer 5: nodriver not available")
        return None
    
    browser = None
    try:
        browser_args = []
        if proxy:
            # Convert socks5://host:port to proxy-server format
            browser_args.append(f"--proxy-server={proxy}")
        
        browser = await uc.start(
            headless=True,
            browser_args=browser_args,
        )
        
        page = await browser.get(url)
        # Wait for page to fully load (CF challenge takes time)
        await asyncio.sleep(3)
        
        # Wait for body content
        try:
            await page.wait_for("body", timeout=timeout)
        except Exception:
            pass
        
        html = await page.get_content()
        
        if _is_blocked(html, 200):
            # Give extra time for CF challenge
            await asyncio.sleep(5)
            html = await page.get_content()
            if _is_blocked(html, 200):
                logger.info(f"Layer 5 blocked for {url}")
                return None
        
        return html
    except Exception as e:
        logger.warning(f"Layer 5 error for {url}: {e}")
        return None
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


async def _layer6_patchright(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 6: patchright stealth Playwright (no Runtime.enable leak)."""
    try:
        from patchright.async_api import async_playwright
    except ImportError:
        logger.warning("Layer 6: patchright not available")
        return None
    
    try:
        async with async_playwright() as p:
            launch_kwargs: Dict[str, Any] = {
                "headless": True,
            }
            if proxy:
                # Parse proxy for Playwright format
                launch_kwargs["proxy"] = {"server": proxy}
            
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="pl-PL",
                timezone_id="Europe/Warsaw",
                user_agent=get_random_ua(),
            )
            
            page = await context.new_page()
            
            response = await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
            
            # Wait for dynamic content
            await asyncio.sleep(2)
            
            html = await page.content()
            status_code = response.status if response else 200
            
            if _is_blocked(html, status_code):
                # Wait for challenge resolution
                await asyncio.sleep(5)
                html = await page.content()
                if _is_blocked(html, status_code):
                    logger.info(f"Layer 6 blocked for {url}")
                    await browser.close()
                    return None
            
            await browser.close()
            return html
    except Exception as e:
        logger.warning(f"Layer 6 error for {url}: {e}")
        try:
            if 'browser' in dir() and browser:
                await browser.close()
        except Exception:
            pass
        return None


async def _layer7_jina(url: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
    """Layer 7: Jina relay (r.jina.ai) - renders JS, returns clean content."""
    try:
        import httpx
    except ImportError:
        logger.warning("Layer 7: httpx not available for Jina relay")
        return None
    
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "text/html",
        "X-Return-Format": "html",
    }
    
    try:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=timeout + 10,  # Jina needs extra time
            proxy=proxy,
        ) as client:
            response = await client.get(jina_url)
            if response.status_code == 200 and response.text:
                if not _is_blocked(response.text, response.status_code):
                    return response.text
            logger.info(f"Layer 7 Jina failed for {url} (status={response.status_code})")
            return None
    except Exception as e:
        logger.warning(f"Layer 7 error for {url}: {e}")
        return None


async def _layer8_skip(url: str, portal_name: str = "unknown") -> None:
    """Layer 8: Skip and report - all layers exhausted."""
    logger.error(
        f"ALL STEALTH LAYERS EXHAUSTED for {url} (portal={portal_name}). "
        f"Manual intervention required."
    )


async def fetch_with_stealth(
    url: str,
    portal_config: Dict[str, Any],
) -> Optional[str]:
    """
    Fetch URL using escalating stealth layers.
    
    Args:
        url: Target URL to fetch
        portal_config: Configuration dict with keys:
            - stealth_layer: Starting layer (1-7)
            - use_tor: Whether to use Tor SOCKS5 proxy
            - tor_proxy: Tor proxy address (default socks5://127.0.0.1:9050)
            - timeout: Request timeout in seconds
            - portal_name: Name of the portal (for logging)
    
    Returns:
        HTML content string or None if all layers failed
    """
    start_layer = portal_config.get("stealth_layer", 1)
    use_tor = portal_config.get("use_tor", False)
    tor_proxy = portal_config.get("tor_proxy", "socks5://127.0.0.1:9050")
    timeout = portal_config.get("timeout", 20.0)
    portal_name = portal_config.get("portal_name", "unknown")
    
    proxy = tor_proxy if use_tor else None
    
    # Layer functions in order
    layers = [
        ("Layer 1: httpx+Chrome", lambda: _layer1_httpx(url, proxy, timeout)),
        ("Layer 2: UA rotation", lambda: _layer2_ua_rotation(url, proxy, timeout)),
        ("Layer 3: curl_cffi", lambda: _layer3_curl_cffi(url, proxy, timeout)),
        ("Layer 4: primp Rust", lambda: _layer4_primp(url, proxy, timeout)),
        ("Layer 5: nodriver CDP", lambda: _layer5_nodriver(url, proxy, timeout)),
        ("Layer 6: patchright", lambda: _layer6_patchright(url, proxy, timeout)),
        ("Layer 7: Jina relay", lambda: _layer7_jina(url, proxy, timeout)),
    ]
    
    # Start from the configured layer (0-indexed internally)
    for i in range(start_layer - 1, len(layers)):
        layer_name, layer_fn = layers[i]
        logger.info(f"[{portal_name}] Trying {layer_name} for {url}")
        
        try:
            result = await layer_fn()
            if result:
                logger.info(f"[{portal_name}] {layer_name} succeeded for {url}")
                return result
        except Exception as e:
            logger.warning(f"[{portal_name}] {layer_name} exception: {e}")
            continue
    
    # Layer 8: All exhausted
    await _layer8_skip(url, portal_name)
    return None
