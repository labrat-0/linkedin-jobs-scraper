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
from src.utils import RateLimiter, fetch_html


def make_scraper(config, page_cards, dead_pages=()):
    """Build a scraper with network + parse patched.

    page_cards: dict {start_offset: [card_dicts]}. Missing offset => empty page.
    dead_pages: offsets whose fetch returns None (simulates an exhausted-retry
                block, e.g. a 451 on every attempt).
    Records fetched offsets in scraper._fetched (order of completion irrelevant).
    """
    scraper = LinkedInJobsScraper(client=None, rate_limiter=RateLimiter(interval=0), config=config)
    scraper._fetched = []
    scraper._dead_pages = set(dead_pages)

    async def fake_fetch(params, start, status_out=None):
        scraper._fetched.append(start)
        if start in scraper._dead_pages:
            if status_out is not None:
                status_out.append(451)
            return None
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


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text
        self.content = text.encode()
        self.headers = {}


class FakeClient:
    """Records each GET and replays a scripted status sequence."""

    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = 0

    async def get(self, url, **kwargs):
        self.calls += 1
        status = self.statuses.pop(0) if self.statuses else 500
        return FakeResponse(status, "OK" if status == 200 else "")

    async def aclose(self):
        pass


class FakeProxyConfig:
    """Hands out a new URL per rotation and counts how often it was asked."""

    def __init__(self):
        self.rotations = 0

    async def new_url(self):
        self.rotations += 1
        return f"http://proxy-{self.rotations}.example"


async def test_451_rotates_and_retries():
    """451 must rotate the proxy and retry, not burn the whole budget in one shot.

    Regression: 451 fell through to the terminal 'Unexpected status' branch, so a
    geo/legal block on one exit IP returned None immediately with the retry budget
    (and every remaining proxy IP) untouched.
    """
    import src.utils as utils

    original_sleep = utils.asyncio.sleep
    original_client_cls = utils.httpx.AsyncClient

    async def no_sleep(_):
        return None

    # A rotation builds a fresh AsyncClient around the new proxy URL. Hand back the
    # same scripted fake so the status sequence continues across rotations.
    holder: dict[str, FakeClient] = {}
    utils.asyncio.sleep = no_sleep
    utils.httpx.AsyncClient = lambda **kwargs: holder["client"]
    try:
        client = FakeClient([451, 451, 200])
        holder["client"] = client
        proxy = FakeProxyConfig()
        statuses: list[int] = []
        html = await fetch_html(
            client, "https://example.test", RateLimiter(interval=0),
            proxy_config=proxy, status_out=statuses, max_retries=5,
        )
        assert html == "OK", f"expected recovery after rotation, got {html!r}"
        assert client.calls == 3, f"expected 3 attempts, got {client.calls}"
        assert proxy.rotations == 2, f"expected 2 proxy rotations, got {proxy.rotations}"
        assert statuses == [451, 451, 200], f"status trail wrong: {statuses}"

        # And when every attempt is 451, the caller learns the real status code.
        client = FakeClient([451, 451])
        holder["client"] = client
        statuses = []
        html = await fetch_html(
            client, "https://example.test", RateLimiter(interval=0),
            proxy_config=FakeProxyConfig(), status_out=statuses, max_retries=2,
        )
        assert html is None
        assert statuses == [451, 451], f"status trail wrong: {statuses}"
    finally:
        utils.asyncio.sleep = original_sleep
        utils.httpx.AsyncClient = original_client_cls
    print("PASS test_451_rotates_and_retries")


async def test_blocked_first_page_skips_only_that_combo():
    """A dead page 0 must skip its combo, not abort the remaining combos.

    Regression: run b7TRSUFMb8wuy7rsS aborted after combo 16 of 30 because a single
    451 on one combo's first page raised out of the batch loop.
    """
    pages = {s: [card(s + i) for i in range(10)] for s in range(0, 250, 25)}
    cfg = ScraperInput(keywords_list=["a", "b", "c"], locations_list=["US"],
                       fetch_job_details=False, max_results=1000,
                       max_results_per_search=10)
    sc = make_scraper(cfg, pages, dead_pages={0})

    # Kill page 0 only while the FIRST combo runs, then let the rest succeed.
    combos_started = []
    real_scrape_single = sc._scrape_single

    def scrape_single(keywords, location, seen_ids, label=""):
        combos_started.append(keywords)
        sc._dead_pages.clear()
        if keywords == "a":
            sc._dead_pages.add(0)
        return real_scrape_single(keywords, location, seen_ids, label)

    sc._scrape_single = scrape_single

    jobs = [j async for j in sc.scrape()]
    assert combos_started == ["a", "b", "c"], \
        f"all 3 combos must run, got {combos_started}"
    assert sc.failed_combos and len(sc.failed_combos) == 1, \
        f"expected 1 failed combo, got {sc.failed_combos}"
    assert len(jobs) == 10, f"surviving combos must still yield, got {len(jobs)}"
    print("PASS test_blocked_first_page_skips_only_that_combo")


async def test_all_combos_blocked_fails_run():
    """If EVERY combo's first page is dead, the run must still fail loudly."""
    cfg = ScraperInput(keywords_list=["a", "b"], locations_list=["US"],
                       fetch_job_details=False, max_results=1000,
                       max_results_per_search=10)
    sc = make_scraper(cfg, {}, dead_pages={0})
    try:
        [j async for j in sc.scrape()]
    except RuntimeError as e:
        assert "all 2 search combination" in str(e), f"unexpected message: {e}"
        print("PASS test_all_combos_blocked_fails_run")
        return
    raise AssertionError("expected RuntimeError when every combo is blocked")


def detail_card(job_id, seniority="", employment=""):
    """A card as it looks AFTER detail enrichment (criteria fields populated)."""
    c = card(job_id)
    c["seniorityLevel"] = seniority
    c["employmentType"] = employment
    return c


def make_enriched_scraper(config, page_cards):
    """Scraper whose enrichment is a no-op — cards already carry criteria fields.

    Detail filters run on post-enrichment rows, so the fields must be present
    without a real detail fetch.
    """
    sc = make_scraper(config, page_cards)

    async def fake_enrich(job):
        return job

    sc._enrich = fake_enrich
    return sc


async def test_experience_filter_drops_mismatch_and_unpublished():
    """experienceLevel keeps only rows LinkedIn published as that seniority.

    Guards the real defect: LinkedIn accepts f_E and ignores it, so the filter
    has to be enforced here. A row whose seniority is absent or "Not Applicable"
    cannot be shown to match and is dropped — counted apart from a true mismatch
    so a thin result set can be explained.
    """
    pages = {0: [
        detail_card(1, seniority="Director", employment="Full-time"),
        detail_card(2, seniority="Entry level", employment="Full-time"),
        detail_card(3, seniority="Not Applicable", employment="Full-time"),
        detail_card(4, seniority="", employment="Full-time"),
        detail_card(5, seniority="Director", employment="Full-time"),
    ]}
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=True,
                       max_results=10, max_results_per_search=10, experience_level="5")
    sc = make_enriched_scraper(cfg, pages)
    jobs = await collect(sc)

    assert [j["jobId"] for j in jobs] == ["1", "5"], \
        f"expected only the Director rows, got {[j['jobId'] for j in jobs]}"
    assert all(j["seniorityLevel"] == "Director" for j in jobs), \
        "a returned row did not actually carry the requested seniority"
    assert sc.dropped_mismatch == 1, f"expected 1 mismatch, got {sc.dropped_mismatch}"
    assert sc.dropped_unpublished == 2, \
        f"expected 2 unpublished, got {sc.dropped_unpublished}"
    print("PASS test_experience_filter_drops_mismatch_and_unpublished")


async def test_job_type_filter_matches_employment_type():
    """jobType keeps only rows whose published Employment type matches."""
    pages = {0: [
        detail_card(1, seniority="Associate", employment="Full-time"),
        detail_card(2, seniority="Associate", employment="Contract"),
        detail_card(3, seniority="Associate", employment="Internship"),
    ]}
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=True,
                       max_results=10, max_results_per_search=10, job_type="C")
    sc = make_enriched_scraper(cfg, pages)
    jobs = await collect(sc)

    assert [j["jobId"] for j in jobs] == ["2"], \
        f"expected only the Contract row, got {[j['jobId'] for j in jobs]}"
    assert sc.dropped_mismatch == 2, f"expected 2 mismatches, got {sc.dropped_mismatch}"
    print("PASS test_job_type_filter_matches_employment_type")


async def test_no_detail_filters_keeps_everything():
    """Without jobType/experienceLevel, rows pass through untouched and uncounted."""
    pages = {0: [
        detail_card(1, seniority="Not Applicable", employment="Full-time"),
        detail_card(2, seniority="Director", employment="Contract"),
    ]}
    cfg = ScraperInput(keywords="x", location="US", fetch_job_details=True,
                       max_results=10, max_results_per_search=10)
    sc = make_enriched_scraper(cfg, pages)
    jobs = await collect(sc)

    assert len(jobs) == 2, f"expected both rows, got {len(jobs)}"
    assert sc.dropped_mismatch == 0 and sc.dropped_unpublished == 0, "nothing should be counted"
    print("PASS test_no_detail_filters_keeps_everything")


async def test_search_params_omit_ignored_filters():
    """Only f_TPR is sent. LinkedIn discards f_WT/f_E/f_JT/f_SB2, so we don't send them.

    Regression guard for the original bug: a mocked-network test can never prove
    a remote API honours a param, so the actor must not derive output from one.
    """
    cfg = ScraperInput(keywords="x", location="US", date_posted="past_week",
                       job_type="F", experience_level="5")
    params = cfg.build_search_params("x", "US")
    assert params.get("f_TPR") == "r604800", f"date filter missing: {params}"
    for dead in ("f_WT", "f_E", "f_JT", "f_SB2"):
        assert dead not in params, f"{dead} is ignored by LinkedIn and must not be sent"
    print("PASS test_search_params_omit_ignored_filters")


async def main():
    await test_order_and_cap()
    await test_dedup_stops_on_exhaustion()
    await test_filter_early_stop_bounded()
    await test_page0_solo()
    await test_parallel_window()
    await test_451_rotates_and_retries()
    await test_blocked_first_page_skips_only_that_combo()
    await test_all_combos_blocked_fails_run()
    await test_experience_filter_drops_mismatch_and_unpublished()
    await test_job_type_filter_matches_employment_type()
    await test_no_detail_filters_keeps_everything()
    await test_search_params_omit_ignored_filters()
    print("\nALL PASSED")


if __name__ == "__main__":
    asyncio.run(main())
