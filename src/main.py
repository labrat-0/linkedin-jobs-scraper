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

        # jobType / experienceLevel are enforced against the detail page's criteria
        # list (LinkedIn discards f_JT and f_E server-side), so they cannot work
        # without it. Turn detail fetching on rather than silently returning
        # unfiltered rows.
        if config.has_detail_filters() and not config.fetch_job_details:
            config.fetch_job_details = True
            Actor.log.info(
                "'Fetch Full Job Details' switched ON automatically: jobType and "
                "experienceLevel are applied to each job's published Employment "
                "type / Seniority level, which only the detail page carries. This "
                "adds one request per job."
            )

        max_results = config.max_results
        if not is_paying and os.environ.get("APIFY_IS_AT_HOME") == "1":
            max_results = min(max_results, FREE_TIER_LIMIT)
            config.max_results = max_results
            config.max_results_per_search = min(config.max_results_per_search, FREE_TIER_LIMIT)
            # Disable detail fetching for free users — halves request count,
            # reduces block exposure, and keeps free runs fast and reliable.
            config.fetch_job_details = False
            config.fetch_company_details = False
            # Without detail pages there is nothing to check jobType /
            # experienceLevel against. Clear them instead of dropping every row
            # for "unpublished" — an empty dataset would be the wrong answer.
            if config.has_detail_filters():
                config.job_type = ""
                config.experience_level = ""
                Actor.log.warning(
                    "jobType / experienceLevel are IGNORED on the free tier: they "
                    "are verified against each job's detail page, which the free "
                    "tier does not fetch. Results are unfiltered by those fields."
                )
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
            # Company enrichment adds extra company-page fetches on top of detail
            # pages. Until a dedicated event can be added (Apify allows one price
            # change per 30 days), bill it under the existing enriched-result event.
            enriched = config.fetch_job_details or config.fetch_company_details

            async def push_batch(items: list[dict]) -> None:
                if not items:
                    return
                await Actor.push_data(items)
                if enriched:
                    await Actor.charge(event_name="enriched-result", count=len(items))

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

        # 6. A run that reached LinkedIn on no combination at all is a failure, not a
        # zero-result success. Reporting it as SUCCEEDED hides a blocked run behind an
        # empty dataset and sends users looking for a filter problem they don't have.
        if (
            count == 0
            and scraper.total_combos
            and len(scraper.failed_combos) == scraper.total_combos
        ):
            await Actor.fail(
                status_message=(
                    f"LinkedIn blocked every one of the {scraper.total_combos} search "
                    "combination(s) — no results could be fetched. The per-combo "
                    "warnings above show the status codes returned. Retry, or switch "
                    "proxy group/region if it persists."
                )
            )
            return

        # 7. Final status message
        msg = f"Done. Scraped {count} jobs."
        if state["failed"] > 0:
            msg += f" {state['failed']} errors encountered."
        # A partially-degraded batch run must say so — otherwise a short result count
        # looks like "LinkedIn had nothing" instead of "some searches never ran".
        if scraper.failed_combos:
            msg += (
                f" {len(scraper.failed_combos)} of {scraper.total_combos} search"
                " combination(s) were skipped because LinkedIn blocked their first"
                " page; re-run to retry those."
            )
        # Client-side filtering can cut a result set well below maxResults. Say by
        # how much and why, so a short run reads as "the filter worked" rather than
        # "the scraper missed jobs".
        if scraper.dropped_mismatch or scraper.dropped_unpublished:
            msg += (
                f" {scraper.dropped_mismatch + scraper.dropped_unpublished} job(s)"
                " were dropped by the jobType/experienceLevel filter:"
                f" {scraper.dropped_mismatch} did not match, and"
                f" {scraper.dropped_unpublished} had no published Employment type /"
                " Seniority level to check (LinkedIn omits seniority on roughly half"
                " of postings)."
            )
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
