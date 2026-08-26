"""Live test of OLX, Otodom, and Morizon scrapers."""
import asyncio
import logging
import sys
import traceback
import time
from typing import List

# Setup logging to see stealth layer activity
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

sys.path.insert(0, "/home/ubuntu/udzialy-bot")

KEYWORDS = ["udział", "współwłasność"]


async def test_olx():
    """Test OLX scraper."""
    print("\n" + "=" * 60)
    print("TESTING: OLX.pl")
    print("=" * 60)
    start = time.time()
    try:
        from scraper.portals.olx import OlxScraper
        scraper = OlxScraper()
        results = await scraper.search(keywords=KEYWORDS)
        elapsed = time.time() - start
        print(f"STATUS: WORKS")
        print(f"RESULTS: {len(results)} listings")
        print(f"TIME: {elapsed:.1f}s")
        if results:
            print(f"SAMPLE (first result):")
            for k, v in results[0].items():
                print(f"  {k}: {repr(v)[:100]}")
            print(f"OUTPUT FORMAT: List[dict] with keys: {list(results[0].keys())}")
        else:
            print("WARNING: 0 results returned (may be blocked or selectors broken)")
        return {"status": "WORKS", "count": len(results), "error": None, "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        tb = traceback.format_exc()
        print(f"STATUS: BROKEN")
        print(f"ERROR: {type(e).__name__}: {e}")
        print(f"TRACEBACK:\n{tb}")
        return {"status": "BROKEN", "count": 0, "error": str(e), "time": elapsed, "traceback": tb}


async def test_otodom():
    """Test Otodom scraper."""
    print("\n" + "=" * 60)
    print("TESTING: Otodom.pl")
    print("=" * 60)
    start = time.time()
    try:
        from scraper.portals.otodom import OtodomScraper
        scraper = OtodomScraper()
        results = await scraper.search(keywords=KEYWORDS)
        elapsed = time.time() - start
        print(f"STATUS: WORKS")
        print(f"RESULTS: {len(results)} listings")
        print(f"TIME: {elapsed:.1f}s")
        if results:
            print(f"SAMPLE (first result):")
            for k, v in results[0].items():
                print(f"  {k}: {repr(v)[:100]}")
            print(f"OUTPUT FORMAT: List[dict] with keys: {list(results[0].keys())}")
        else:
            print("WARNING: 0 results returned (may be blocked or __NEXT_DATA__ missing)")
        return {"status": "WORKS", "count": len(results), "error": None, "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        tb = traceback.format_exc()
        print(f"STATUS: BROKEN")
        print(f"ERROR: {type(e).__name__}: {e}")
        print(f"TRACEBACK:\n{tb}")
        return {"status": "BROKEN", "count": 0, "error": str(e), "time": elapsed, "traceback": tb}


async def test_morizon():
    """Test Morizon scraper."""
    print("\n" + "=" * 60)
    print("TESTING: Morizon.pl")
    print("=" * 60)
    start = time.time()
    try:
        from scraper.portals.morizon import MorizonScraper
        scraper = MorizonScraper()
        results = await scraper.search(keywords=KEYWORDS)
        elapsed = time.time() - start
        print(f"STATUS: WORKS")
        print(f"RESULTS: {len(results)} listings")
        print(f"TIME: {elapsed:.1f}s")
        if results:
            print(f"SAMPLE (first result):")
            for k, v in results[0].items():
                print(f"  {k}: {repr(v)[:100]}")
            print(f"OUTPUT FORMAT: List[dict] with keys: {list(results[0].keys())}")
        else:
            print("WARNING: 0 results returned (may be blocked or selectors broken)")
        return {"status": "WORKS", "count": len(results), "error": None, "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        tb = traceback.format_exc()
        print(f"STATUS: BROKEN")
        print(f"ERROR: {type(e).__name__}: {e}")
        print(f"TRACEBACK:\n{tb}")
        return {"status": "BROKEN", "count": 0, "error": str(e), "time": elapsed, "traceback": tb}


async def main():
    print("=" * 60)
    print("LIVE SCRAPER TEST - udzialy-bot")
    print(f"Keywords: {KEYWORDS}")
    print("=" * 60)

    # Run each scraper sequentially (to avoid resource conflicts)
    olx_result = await test_olx()
    otodom_result = await test_otodom()
    morizon_result = await test_morizon()

    # Final summary
    print("\n\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    for name, result in [("OLX", olx_result), ("Otodom", otodom_result), ("Morizon", morizon_result)]:
        status = result["status"]
        count = result["count"]
        error = result.get("error", "")
        t = result.get("time", 0)
        err_str = f" | ERROR: {error[:80]}" if error else ""
        print(f"  {name:10s}: {status:7s} | {count:3d} results | {t:.1f}s{err_str}")


if __name__ == "__main__":
    asyncio.run(main())
