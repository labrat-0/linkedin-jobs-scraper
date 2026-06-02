"""Utility functions for rate limiting, retries, and HTTP helpers."""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# Politeness delay applied (with jitter) before each request. A fresh residential
# IP is used per retry and concurrent requests fan out across the proxy pool, so a
# short interval is safe — unlike a hard 5s global serial wait, which billed huge
# amounts of idle compute (Apify bills memory × wall-time, sleeps included).
REQUEST_INTERVAL = 1.5

# Max in-flight requests at once. Bounds concurrency so enrichment (one detail page
# per job) fans out instead of running serially, cutting wall-time ~3-5x on detail
# runs while keeping load on LinkedIn reasonable.
MAX_CONCURRENCY = 5

# Retry settings
# Kept low intentionally: 2 retries × (5+10)s = 15s max wait per URL.
# Old values (3 retries × 15+30+60s = 105s) caused run timeouts on blocked IPs.
MAX_RETRIES = 2
RETRY_BASE_DELAY = 5.0  # seconds


class BudgetExceededError(Exception):
    """Raised when a run exceeds its proxy data budget — abort to cap cost."""


class ByteBudget:
    """Tracks cumulative downloaded bytes and aborts a run if it blows past a cap.

    Residential proxy traffic (~$8/GB) is the dominant variable cost. With no
    per-run price floor, a pathological run (block loop, huge pages, runaway
    pagination) could download far more than its results are worth. This rail
    aborts such runs in seconds instead of letting them bleed proxy spend.
    """

    def __init__(self, limit_bytes: int) -> None:
        self.limit = limit_bytes
        self.used = 0

    def add(self, n: int) -> None:
        self.used += n
        if self.used > self.limit:
            raise BudgetExceededError(
                f"Proxy data budget exceeded ({self.used:,} > {self.limit:,} bytes). "
                "Aborting to prevent runaway proxy cost. "
                "Lower maxResults or disable enrichment and re-run."
            )

# User agents to rotate through (realistic browser UAs — updated 2026)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
]

BASE_URL = "https://www.linkedin.com"
GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


class RateLimiter:
    """Concurrency gate with a jittered politeness delay.

    Replaces the old serial 5s-between-requests lock. A semaphore bounds how many
    requests are in flight at once (so enrichment can fan out), and each acquired
    slot waits a short jittered interval to avoid synchronized bursts.
    """

    def __init__(
        self,
        interval: float = REQUEST_INTERVAL,
        concurrency: int = MAX_CONCURRENCY,
    ) -> None:
        self._interval = interval
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _delay(self) -> None:
        if self._interval > 0:
            wait_time = random.uniform(self._interval * 0.5, self._interval * 1.5)
            logger.debug(f"Rate limiter: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire a concurrency slot, applying the politeness delay before use."""
        async with self._semaphore:
            await self._delay()
            yield

    async def wait(self) -> None:
        """Backward-compatible delay (no concurrency gate). Prefer slot()."""
        await self._delay()


def get_headers() -> dict[str, str]:
    """Return headers for page navigation requests (job detail pages)."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.linkedin.com/jobs/search/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }


def get_api_headers() -> dict[str, str]:
    """Return headers for AJAX calls to the guest API endpoint.

    The guest API is fetched via JavaScript (XHR/fetch), not a page navigation,
    so Sec-Fetch headers must reflect that. Using document/navigate headers here
    is a bot signal LinkedIn detects.
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.linkedin.com/jobs/search/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


async def fetch_html(
    client: httpx.AsyncClient,
    url: str,
    rate_limiter: RateLimiter,
    params: dict[str, str] | None = None,
    api_request: bool = False,
    proxy_config=None,
    byte_budget: ByteBudget | None = None,
) -> str | None:
    """Fetch HTML from a URL with rate limiting, retry logic, and proxy rotation.

    Args:
        api_request: If True, use AJAX/XHR headers (for the guest API endpoint).
                     If False, use page navigation headers (for detail pages).
        proxy_config: Apify ProxyConfiguration instance. When provided, a fresh
                      proxy IP is requested from the pool on each 403/429 retry
                      instead of hitting the same blocked IP again.
        byte_budget: Optional ByteBudget. Downloaded bytes are counted against it;
                     it raises BudgetExceededError once the run cap is hit.

    Returns the HTML string, or None if all retries fail.

    Raises:
        BudgetExceededError: if the cumulative proxy data budget is exceeded.
    """
    for attempt in range(MAX_RETRIES):
        # On retries after a block: get a fresh proxy IP from the pool.
        # First attempt uses the shared client (existing IP). Subsequent
        # attempts spin up a short-lived client with a new proxy URL so
        # LinkedIn sees a different IP instead of the same blocked one.
        active_client = client
        temp_client: httpx.AsyncClient | None = None
        if attempt > 0 and proxy_config is not None:
            try:
                new_proxy_url = await proxy_config.new_url()
                temp_client = httpx.AsyncClient(proxy=new_proxy_url)
                active_client = temp_client
                logger.debug(f"Proxy rotated for retry {attempt + 1}/{MAX_RETRIES}")
            except Exception as e:
                logger.warning(f"Failed to rotate proxy: {e} — reusing existing client")

        try:
            async with rate_limiter.slot():
                response = await active_client.get(
                    url,
                    params=params,
                    headers=get_api_headers() if api_request else get_headers(),
                    timeout=30.0,
                    follow_redirects=True,
                )

            if byte_budget is not None:
                byte_budget.add(len(response.content))

            if response.status_code == 200:
                logger.debug(
                    f"OK 200 | url={url} | length={len(response.text)} | "
                    f"content_type={response.headers.get('content-type', 'unknown')}"
                )
                return response.text

            if response.status_code == 429:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Rate limited (429) on {url}. "
                    f"Rotating proxy and retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code == 403:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Forbidden (403) on {url}. "
                    f"Rotating proxy and retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code == 400:
                # LinkedIn returns 400 when pagination exceeds limit (start >= 1000)
                logger.info(f"Bad request (400) on {url} -- likely pagination limit reached")
                return None

            if response.status_code == 404:
                logger.warning(f"Not found (404): {url}")
                return None

            if response.status_code >= 500:
                delay = 10.0 * (attempt + 1)
                logger.warning(
                    f"Server error ({response.status_code}) on {url}. "
                    f"Retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                continue

            logger.warning(f"Unexpected status {response.status_code} on {url}")
            return None

        except httpx.TimeoutException:
            delay = 10.0 * (attempt + 1)
            logger.warning(
                f"Timeout on {url}. "
                f"Retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            await asyncio.sleep(delay)
            continue

        except httpx.HTTPError as e:
            delay = 10.0 * (attempt + 1)
            logger.warning(
                f"HTTP error on {url}: {e}. "
                f"Retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            await asyncio.sleep(delay)
            continue

        finally:
            if temp_client is not None:
                await temp_client.aclose()

    logger.error(f"All {MAX_RETRIES} retries exhausted for {url}")
    return None
