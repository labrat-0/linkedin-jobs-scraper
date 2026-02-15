"""Utility functions for rate limiting, retries, and HTTP helpers."""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

logger = logging.getLogger(__name__)

# LinkedIn is stricter than Reddit. We use 5 seconds between requests
# to stay under the radar with residential proxies.
REQUEST_INTERVAL = 5.0

# Retry settings
MAX_RETRIES = 3
RETRY_BASE_DELAY = 15.0  # seconds

# User agents to rotate through (realistic browser UAs)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

BASE_URL = "https://www.linkedin.com"
GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


class RateLimiter:
    """Simple rate limiter that ensures a minimum interval between requests."""

    def __init__(self, interval: float = REQUEST_INTERVAL) -> None:
        self._interval = interval
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait until it's safe to make another request."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request
            if elapsed < self._interval:
                wait_time = self._interval - elapsed
                logger.debug(f"Rate limiter: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
            self._last_request = asyncio.get_event_loop().time()


def get_headers() -> dict[str, str]:
    """Return headers with a random User-Agent for HTML requests."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


async def fetch_html(
    client: httpx.AsyncClient,
    url: str,
    rate_limiter: RateLimiter,
    params: dict[str, str] | None = None,
) -> str | None:
    """Fetch HTML from a URL with rate limiting and retry logic.

    Returns the HTML string, or None if all retries fail.
    """
    for attempt in range(MAX_RETRIES):
        await rate_limiter.wait()

        try:
            response = await client.get(
                url,
                params=params,
                headers=get_headers(),
                timeout=30.0,
                follow_redirects=True,
            )

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
                    f"Retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code == 403:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Forbidden (403) on {url}. "
                    f"IP may be blocked. Retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
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

    logger.error(f"All {MAX_RETRIES} retries exhausted for {url}")
    return None
