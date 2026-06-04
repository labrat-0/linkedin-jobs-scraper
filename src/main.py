"""LinkedIn Jobs Scraper -- Apify Actor entry point."""

from __future__ import annotations

import logging
import os

import httpx
from apify import Actor

from .models import ScraperInput
from .scraper import LinkedInJobsScraper
from .utils import BudgetExceededError, RateLimiter

logger = logging.getLogger(__name__)

# Free tier limit
FREE_TIER_LIMIT = 25

# Actor owner's Apify user id. Lets the owner run the full paying-user path on the
# platform without a paid plan, for testing. Safe to keep in a public repo: a user
# id is not a secret, and APIFY_USER_ID is set by the platform (not user-supplied),
# so a renter cannot forge it to unlock paid features for free.
OWNER_USER_ID = "wCP1WauwRX2Gr3Gir"


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
        # Log who started the run so the owner can find their Apify user id (needed
        # to set DEV_PAYING_USER_ID below).
        user_id = os.environ.get("APIFY_USER_ID", "")
        Actor.log.info(f"Run started by user: {user_id or 'unknown (local?)'}")

        # Dev/testing override: lets the actor OWNER exercise the full paying-user
        # path on the platform without a paid subscription. Set DEV_PAYING_USER_ID
        # (actor env var) to your own Apify user id; the bypass activates only when
        # it matches the user who started the run, so it is safe to leave enabled —
        # other users still get the normal free/paid gate.
        dev_paying_uid = os.environ.get("DEV_PAYING_USER_ID", "").strip()
        owner_override = (
            (bool(OWNER_USER_ID) and user_id == OWNER_USER_ID)
            or (bool(dev_paying_uid) and user_id == dev_paying_uid)
        )

        is_paying = owner_override or (
            os.environ.get("APIFY_IS_AT_HOME") == "1"
            and os.environ.get("APIFY_USER_IS_PAYING") == "1"
        )
        if owner_override:
            Actor.log.info(
                "DEV override: run owner matches DEV_PAYING_USER_ID — "
                "full paying-user features enabled (testing only)."
            )

        # Did the user ask for enrichment that the free gate will strip? Tell them.
        requested_enrichment = config.fetch_job_details or config.fetch_company_details

        max_results = config.max_results
        if not is_paying and os.environ.get("APIFY_IS_AT_HOME") == "1":
            max_results = min(max_results, FREE_TIER_LIMIT)
            config.max_results = max_results
            config.max_results_per_search = min(config.max_results_per_search, FREE_TIER_LIMIT)
            # Disable detail fetching for free users — halves request count,
            # reduces block exposure, and keeps free runs fast and reliable.
            config.fetch_job_details = False
            config.fetch_company_details = False
            if requested_enrichment:
                Actor.log.warning(
                    "Fetch Full Job Details was requested but is DISABLED on the "
                    "free tier — returning listing data only."
                )
            Actor.log.info(
                f"Free tier: limited to {FREE_TIER_LIMIT} results (listing data only). "
                "Subscribe for full job details: description, seniority, employment type, "
                "job function, industry, and applicant count."
            )
        elif not config.fetch_job_details:
            # Paying/local run with detail fetch off. The detail-only fields
            # (companyEmployeeCount, applicantCount, companyIndustry, description,
            # seniority, employment type, job function) come back empty unless this
            # is enabled — warn so it doesn't look like missing data.
            Actor.log.warning(
                "'Fetch Full Job Details' is OFF — companyIndustry, applicantCount, "
                "companyEmployeeCount, description, seniority, employmentType and "
                "jobFunction will be empty. Set \"fetchJobDetails\": true to populate them."
            )

        combos = config.get_search_combos()
        batch_mode = len(combos) > 1
        Actor.log.info(
            f"Starting LinkedIn Jobs Scraper | "
            f"searches={len(combos)} | batch_mode={batch_mode} | "
            f"details={config.fetch_job_details} | "
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

        if not proxy_url and os.environ.get("APIFY_IS_AT_HOME") == "1":
            await Actor.fail(
                status_message=(
                    "Proxy required. LinkedIn blocks datacenter IPs on almost every run. "
                    "Enable Apify Proxy with RESIDENTIAL group in Proxy Configuration and re-run."
                )
            )
            return
        elif not proxy_url:
            Actor.log.warning(
                "No proxy configured. LinkedIn blocks most direct connections. "
                "Continuing for local testing only."
            )

        # 4. Resume state (survives migrations)
        state = await Actor.use_state(
            default_value={"scraped": 0, "failed": 0}
        )

        await Actor.set_status_message("Connecting to LinkedIn...")

        async with httpx.AsyncClient(proxy=proxy_url) as client:
            rate_limiter = RateLimiter()
            scraper = LinkedInJobsScraper(client, rate_limiter, config, proxy_config=proxy_config)

            count = state["scraped"]
            batch: list[dict] = []
            batch_size = 25  # Push in batches for efficiency

            # When enrichment is on, every result cost an extra detail-page fetch
            # (more proxy GB + compute). Charge the `enriched-result` event per item
            # so the price reflects that cost. The `result` (dataset-item) event is
            # auto-charged by push_data on top of this.
            # Company-page enrichment adds extra ~350 KB residential fetches on top of
            # detail pages. Each cache-miss fetch is billed under its own dedicated
            # `company-detail` event (charge_company below), so it is self-funding —
            # the customer pays only for companies actually fetched (cache hits free).
            enriched = config.fetch_job_details or config.fetch_company_details

            charged_company_fetches = 0

            async def push_batch(items: list[dict]) -> None:
                if not items:
                    return
                await Actor.push_data(items)
                if enriched:
                    await Actor.charge(event_name="enriched-result", count=len(items))

            async def charge_company() -> None:
                # Bill the company-page fetches done since the last charge. Reconciled
                # after every push and in `finally`, so partial/blocked/crashed runs
                # still bill the fetches already incurred (mirrors enriched-result).
                nonlocal charged_company_fetches
                delta = scraper.company_fetches - charged_company_fetches
                if delta > 0:
                    await Actor.charge(event_name="company-detail", count=delta)
                    charged_company_fetches = scraper.company_fetches

            try:
                async for item in scraper.scrape():
                    if count >= max_results:
                        break

                    batch.append(item)
                    count += 1
                    state["scraped"] = count

                    # Push in batches
                    if len(batch) >= batch_size:
                        await push_batch(batch)
                        batch = []

                        await Actor.set_status_message(
                            f"Scraped {count}/{max_results} jobs"
                        )

                # Push remaining items
                await push_batch(batch)

            except BudgetExceededError as e:
                # Proxy data cap hit — keep whatever we already scraped and stop.
                await push_batch(batch)
                Actor.log.warning(
                    f"Run stopped early to cap proxy cost: {e} "
                    f"Returned {count} jobs."
                )
                await Actor.set_status_message(
                    f"Stopped at {count} jobs to cap proxy cost. "
                    "Lower maxResults or disable enrichment for larger runs."
                )
                return

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
                await push_batch(batch)

            finally:
                # Bill any company-page fetches not yet charged — runs on every exit
                # path (normal, BudgetExceeded return, exception) so no fetch is free.
                await charge_company()

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
