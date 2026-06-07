"""Offline tests for windowed (parallel) pagination in _scrape_single.

Patches network + parsing so only the pagination/windowing/early-stop logic runs.
Verifies the parallel page-walk preserves serial semantics: yield order, dedup,
result cap, and the early-stop guards.

Run: .venv/bin/python test_pagination.py
"""

import asyncio
import sys

sys.path.insert(0, ".")

from src.models import ScraperInput
from src.scraper import LinkedInJobsScraper, _FILTER_EMPTY_PAGE_LIMIT, _PAGE_WINDOW
from src.utils import RateLimiter


def make_scraper(config, page_cards):
    """Build a scraper with network + parse patched.

    page_cards: dict {start_offset: [card_dicts]}. Missing offset => empty page.
    Records fetched offsets in scraper._fetched (order of completion irrelevant).
    """
    scraper = LinkedInJobsScraper(client=None, rate_limiter=RateLimiter(interval=0), config=config)
    scraper._fetched = []

    async def fake_fetch(params, start):
        scraper._fetched.append(start)
        return f"PAGE{start}"  # non-empty sentinel; parsed below

    def fake_parse(html):
        start = int(html.replace("PAGE", ""))
        return list(page_cards.get(start, []))

    scraper._fetch_search_page = fake_fetch
    scraper._parse_search_cards = fake_parse
    return scraper


def card(job_id, title="Data Analyst"):
    return {"jobId": str(job_id), "title": title, "company": "Acme", "companyUrl": ""}


async def collect(scraper, keywords="", location="United States"):
    seen = set()
    out = []
    async for job in scraper._scrape_single(keywords, location, seen):
        out.append(job)
    return out


async def test_order_and_cap():
    """Unique jobs across pages: order preserved, result cap respected."""
    pages = {s: [card(s + i) for i in range(10)] for s in range(0, 250, 25)}
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=False, max_results=23, max_results_per_search=23)
    sc = make_scraper(cfg, pages)
    jobs = await collect(sc)
    assert len(jobs) == 23, f"cap: expected 23, got {len(jobs)}"
    ids = [j["jobId"] for j in jobs]
    # First 23 cards in page order: page0 ids 0-9, page25 ids 25-34, page50 ids 50-52
    expected = [str(i) for i in range(0, 10)] + [str(i) for i in range(25, 35)] + [str(i) for i in range(50, 53)]
    assert ids == expected, f"order/cap mismatch:\n got {ids}\n exp {expected}"
    print("PASS test_order_and_cap")


async def test_dedup_stops_on_exhaustion():
    """Repeated jobIds (LinkedIn looping) => new_unique==0 => stop."""
    dup = [card(i) for i in range(10)]
    pages = {0: dup, 25: dup, 50: dup}  # same cards repeated
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=False, max_results=1000, max_results_per_search=1000)
    sc = make_scraper(cfg, pages)
    jobs = await collect(sc)
    assert len(jobs) == 10, f"dedup: expected 10 unique, got {len(jobs)}"
    assert len(set(j["jobId"] for j in jobs)) == 10, "duplicates leaked"
    print("PASS test_dedup_stops_on_exhaustion")


async def test_filter_early_stop_bounded():
    """titleOnly with no matches: stop after _FILTER_EMPTY_PAGE_LIMIT, over-fetch bounded."""
    # 100 pages of cards that never match the title filter.
    pages = {s: [card(s + i, title="Nurse") for i in range(10)] for s in range(0, 2500, 25)}
    cfg = ScraperInput(keywords="engineer", location="US", fetch_job_details=False,
                       max_results=1000, max_results_per_search=1000, title_only=True)
    sc = make_scraper(cfg, pages)
    jobs = await collect(sc, keywords="engineer")
    assert len(jobs) == 0, f"expected 0 title matches, got {len(jobs)}"
    # Serial would fetch exactly _FILTER_EMPTY_PAGE_LIMIT pages. Windowed may
    # over-fetch up to _PAGE_WINDOW-1 more (bounded waste, by design).
    n = len(sc._fetched)
    assert _FILTER_EMPTY_PAGE_LIMIT <= n <= _FILTER_EMPTY_PAGE_LIMIT + _PAGE_WINDOW - 1, \
        f"fetched {n}, expected within [{_FILTER_EMPTY_PAGE_LIMIT}, {_FILTER_EMPTY_PAGE_LIMIT + _PAGE_WINDOW - 1}]"
    print(f"PASS test_filter_early_stop_bounded (fetched {n} pages)")


async def test_page0_solo():
    """First batch fetches start=0 alone (point-of-failure gate)."""
    pages = {s: [card(s + i) for i in range(10)] for s in range(0, 250, 25)}
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=False, max_results=5, max_results_per_search=5)
    sc = make_scraper(cfg, pages)
    await collect(sc)
    assert sc._fetched[0] == 0, "page 0 must be fetched first"
    # max_results=5 satisfied on page 0 alone => only page 0 fetched
    assert sc._fetched == [0], f"expected only page 0 fetched, got {sc._fetched}"
    print("PASS test_page0_solo")


async def test_parallel_window():
    """After page 0, pages fetched in a window of _PAGE_WINDOW concurrently."""
    pages = {s: [card(s + i) for i in range(10)] for s in range(0, 2500, 25)}
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=False, max_results=1000, max_results_per_search=1000)
    sc = make_scraper(cfg, pages)
    # Enough unique jobs to keep going; will hit start>=1000 limit (40 pages).
    await collect(sc)
    # First fetch is page 0 solo, then windows of _PAGE_WINDOW.
    assert sc._fetched[0] == 0
    # 1000/25 = 40 pages max (start 0..975). Page 0 solo + windows.
    assert len(sc._fetched) == 40, f"expected 40 pages (LinkedIn limit), got {len(sc._fetched)}"
    print(f"PASS test_parallel_window (fetched {len(sc._fetched)} pages, window={_PAGE_WINDOW})")


async def main():
    await test_order_and_cap()
    await test_dedup_stops_on_exhaustion()
    await test_filter_early_stop_bounded()
    await test_page0_solo()
    await test_parallel_window()
    print("\nALL PASSED")


if __name__ == "__main__":
    asyncio.run(main())
