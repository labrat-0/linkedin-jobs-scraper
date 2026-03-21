"""LinkedIn Jobs Scraper -- Apify Actor entry point."""

from __future__ import annotations

import logging
import os

import httpx
from apify import Actor

from .models import ScraperInput
from .scraper import LinkedInJobsScraper
from .utils import RateLimiter

logger = logging.getLogger(__name__)

# Free tier limit
FREE_TIER_LIMIT = 25


async def main() -> None:
    """Main actor function."""
    async with Actor:
        # 1. Get and validate input
        raw_input = await Actor.get_input() or {}
        config = ScraperInput.from_actor_input(raw_input)

        validation_error = config.validate_input()
        if validation_error:
            await Actor.fail(status_message=validation_error)
            return

        # 2. Handle free user limits
        is_paying = os.environ.get("APIFY_IS_AT_HOME") == "1" and os.environ.get(
            "APIFY_USER_IS_PAYING"
        ) == "1"

        max_results = config.max_results
        if not is_paying and os.environ.get("APIFY_IS_AT_HOME") == "1":
            max_results = min(max_results, FREE_TIER_LIMIT)
            config.max_results = max_results
            config.max_results_per_search = min(config.max_results_per_search, FREE_TIER_LIMIT)
            Actor.log.info(
                f"Free tier: limited to {FREE_TIER_LIMIT} results. "
                "Subscribe to the actor for unlimited results."
            )

        combos = config.get_search_combos()
        batch_mode = len(combos) > 1
        Actor.log.info(
            f"Starting LinkedIn Jobs Scraper | "
            f"searches={len(combos)} | batch_mode={batch_mode} | "
            f"details={config.fetch_job_details} | company_enrichment={config.fetch_company_details} | "
            f"max_results={max_results}"
        )

        # 3. Set up proxy
        proxy_config = None
        proxy_url = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=raw_input.get("proxyConfiguration")
            )
            if proxy_config:
                proxy_url = await proxy_config.new_url()
        except Exception as e:
            Actor.log.warning(f"Failed to create proxy configuration: {e}")

        if not proxy_url:
            Actor.log.warning(
                "No proxy configured. LinkedIn blocks most direct connections. "
                "Consider enabling Apify Proxy with RESIDENTIAL group for reliable scraping."
            )

        # 4. Resume state (survives migrations)
        state = await Actor.use_state(
            default_value={"scraped": 0, "failed": 0}
        )

        await Actor.set_status_message("Connecting to LinkedIn...")

        async with httpx.AsyncClient(proxy=proxy_url) as client:
            rate_limiter = RateLimiter()
            scraper = LinkedInJobsScraper(client, rate_limiter, config)

            count = state["scraped"]
            batch: list[dict] = []
            batch_size = 25  # Push in batches for efficiency

            try:
                async for item in scraper.scrape():
                    if count >= max_results:
                        break

                    batch.append(item)
                    count += 1
                    state["scraped"] = count

                    # Push in batches
                    if len(batch) >= batch_size:
                        await Actor.push_data(batch)
                        batch = []

                        await Actor.set_status_message(
                            f"Scraped {count}/{max_results} jobs"
                        )

                # Push remaining items
                if batch:
                    await Actor.push_data(batch)

            except Exception as e:
                state["failed"] += 1
                error_msg = str(e).lower()
                
                # Provide specific guidance based on error type
                if "403" in error_msg or "forbidden" in error_msg:
                    Actor.log.error(
                        f"LinkedIn blocked the request (403 Forbidden). "
                        "This usually means the IP is blocked. "
                        "Try using RESIDENTIAL proxies or wait before retrying."
                    )
                elif "429" in error_msg or "rate" in error_msg:
                    Actor.log.error(
                        f"LinkedIn rate limited the request (429). "
                        "Too many requests. Wait a few minutes before retrying."
                    )
                elif "timeout" in error_msg:
                    Actor.log.error(
                        f"Request timed out. LinkedIn may be slow or blocking. "
                        "Try again with RESIDENTIAL proxies."
                    )
                else:
                    Actor.log.error(f"Scraping error: {e}")
                
                # Push whatever we have so far
                if batch:
                    await Actor.push_data(batch)

        # 6. Final status message
        msg = f"Done. Scraped {count} jobs."
        if state["failed"] > 0:
            msg += f" {state['failed']} errors encountered."
        if (
            not is_paying
            and os.environ.get("APIFY_IS_AT_HOME") == "1"
            and count >= FREE_TIER_LIMIT
        ):
            msg += (
                f" Free tier limit ({FREE_TIER_LIMIT}) reached."
                " Subscribe for unlimited results."
            )

        Actor.log.info(msg)
        await Actor.set_status_message(msg)
