"""Core LinkedIn Jobs scraping logic. HTML parsing of public job search pages."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator

import httpx
from bs4 import BeautifulSoup, Tag

from .models import ScraperInput, format_job_card
from .utils import (
    GUEST_API_URL,
    GUEST_JOB_DETAIL_URL,
    ByteBudget,
    RateLimiter,
    fetch_html,
)

logger = logging.getLogger(__name__)

# Proxy data budget: floor 25 MB, plus ~0.5 MB per requested result. Generous
# enough for legit enriched runs (detail page ≈ 150-250 KB) while still aborting
# pathological block loops / runaway pagination before they bleed proxy spend.
_BUDGET_FLOOR_BYTES = 25_000_000
_BUDGET_PER_RESULT_BYTES = 500_000


class LinkedInJobsScraper:
    """Scrapes LinkedIn Jobs using public HTML pages (no auth, no cookies, no API key)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: RateLimiter,
        config: ScraperInput,
        proxy_config=None,
    ) -> None:
        self.client = client
        self.rate_limiter = rate_limiter
        self.config = config
        self.proxy_config = proxy_config
        self.byte_budget = ByteBudget(
            _BUDGET_FLOOR_BYTES + config.max_results * _BUDGET_PER_RESULT_BYTES
        )

    async def scrape(self) -> AsyncIterator[dict[str, Any]]:
        """Main entry point — runs all keyword/location search combinations.

        Supports both single search (keywords + location) and batch search
        (keywordsList × locationsList), deduplicating results by jobId across combos.
        """
        combos = self.config.get_search_combos()
        seen_ids: set[str] = set()

        logger.info(f"Starting search: {len(combos)} combination(s)")

        for keywords, location in combos:
            label = f"keywords='{keywords}' location='{location}'"
            logger.info(f"Searching: {label}")
            async for job in self._scrape_single(keywords, location, seen_ids):
                yield job

    async def _scrape_single(
        self,
        keywords: str,
        location: str,
        seen_ids: set[str],
    ) -> AsyncIterator[dict[str, Any]]:
        """Scrape one keyword/location search, paginating through results."""
        params = self.config.build_search_params(keywords, location)
        count = 0
        max_results = self.config.max_results_per_search
        start = 0
        consecutive_empty = 0

        while count < max_results:
            if start >= 1000:
                logger.info("Reached LinkedIn pagination limit (start=1000)")
                break

            page_params = dict(params)
            page_params["start"] = str(start)

            page_html = await fetch_html(
                self.client, GUEST_API_URL, self.rate_limiter, page_params,
                api_request=True, proxy_config=self.proxy_config,
                byte_budget=self.byte_budget,
            )

            if not page_html:
                if start == 0:
                    raise RuntimeError(
                        "Failed to fetch initial results from LinkedIn. "
                        "The IP may be blocked. Try using RESIDENTIAL proxies."
                    )
                logger.info(f"No response at start={start}")
                break

            logger.info(f"Page start={start}: response length={len(page_html)} chars")
            if len(page_html) < 500:
                logger.debug(f"Short response body: {page_html[:500]}")

            if "authwall" in page_html.lower() or "sign in" in page_html[:2000].lower():
                if start == 0:
                    raise RuntimeError(
                        "LinkedIn auth wall detected. Guest access is blocked. "
                        "Try using RESIDENTIAL proxies from a different region."
                    )
                logger.warning(f"Possible auth wall at start={start}, continuing...")

            page_jobs = self._parse_search_cards(page_html)

            if not page_jobs:
                consecutive_empty += 1
                logger.info(
                    f"No job cards at start={start} (consecutive_empty={consecutive_empty})"
                )
                if consecutive_empty >= 2:
                    logger.info("Two consecutive empty pages, stopping pagination")
                    break
                start += 25
                continue

            consecutive_empty = 0
            logger.info(f"Page start={start}: found {len(page_jobs)} job cards")

            # Select this page's jobs (dedup + company filter), capped at the
            # remaining limit so we never enrich more than we'll yield.
            to_process: list[dict[str, Any]] = []
            for job in page_jobs:
                if count + len(to_process) >= max_results:
                    break

                job_id = job.get("jobId", "")
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                # Company filter — match against company name or LinkedIn slug
                if self.config.company_filter:
                    company = job.get("company", "").lower()
                    company_url = job.get("companyUrl", "").lower()
                    if not any(
                        f.lower() in company or f.lower() in company_url
                        for f in self.config.company_filter
                    ):
                        continue

                # Track which search produced this result (useful in batch mode)
                job["searchKeywords"] = keywords
                job["searchLocation"] = location
                to_process.append(job)

            # Enrich the whole page concurrently — detail pages fan out across the
            # proxy pool instead of running one-at-a-time.
            if self.config.fetch_job_details:
                to_process = list(
                    await asyncio.gather(*(self._enrich(j) for j in to_process))
                )

            for job in to_process:
                if count >= max_results:
                    return
                yield format_job_card(job)
                count += 1

            start += 25

    async def _enrich(self, job: dict[str, Any]) -> dict[str, Any]:
        """Run the enabled enrichment passes for a single job."""
        if self.config.fetch_job_details:
            job = await self._enrich_with_details(job)
        return job

    # --- HTML Parsing ---

    def _parse_search_cards(self, html: str) -> list[dict[str, Any]]:
        """Parse job cards from search results HTML."""
        soup = BeautifulSoup(html, "lxml")
        jobs: list[dict[str, Any]] = []

        cards = soup.find_all("div", class_="job-search-card")

        if not cards:
            cards = soup.find_all("li")
            cards = [
                c for c in cards
                if isinstance(c, Tag)
                and c.find("div", attrs={"data-entity-urn": True})
            ]
            unwrapped = []
            for c in cards:
                inner = c.find("div", attrs={"data-entity-urn": True})
                if inner:
                    unwrapped.append(inner)
            if unwrapped:
                cards = unwrapped

        for card in cards:
            if not isinstance(card, Tag):
                continue
            job = self._parse_single_card(card)
            if job and job.get("jobId"):
                jobs.append(job)

        return jobs

    def _parse_single_card(self, card: Tag) -> dict[str, Any]:
        """Parse a single job card element into a dict."""
        job: dict[str, Any] = {}

        # Job ID from data-entity-urn
        urn = card.get("data-entity-urn", "")
        if isinstance(urn, str) and "jobPosting:" in urn:
            job["jobId"] = urn.split("jobPosting:")[-1]
        else:
            urn_el = card.find(attrs={"data-entity-urn": True})
            if urn_el:
                urn_val = urn_el.get("data-entity-urn", "")
                if isinstance(urn_val, str) and "jobPosting:" in urn_val:
                    job["jobId"] = urn_val.split("jobPosting:")[-1]

        if not job.get("jobId"):
            return {}

        # Title
        title_el = card.find("h3", class_=re.compile(r"base-search-card__title"))
        if not title_el:
            title_el = card.find("h3")
        if title_el:
            job["title"] = title_el.get_text(strip=True)

        # Company
        company_el = card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
        if not company_el:
            company_el = card.find("h4")
        if company_el:
            job["company"] = company_el.get_text(strip=True)
            company_link = company_el.find("a")
            if company_link:
                href = company_link.get("href", "")
                if isinstance(href, str):
                    job["companyUrl"] = href.split("?")[0]

        # Location
        location_el = card.find("span", class_=re.compile(r"job-search-card__location"))
        if location_el:
            job["location"] = location_el.get_text(strip=True)

        # Posted date
        time_el = card.find("time")
        if time_el:
            job["postedDateTimestamp"] = time_el.get("datetime", "")
            job["postedDate"] = time_el.get_text(strip=True)

        # Salary (sometimes on card)
        salary_el = card.find("span", class_=re.compile(r"job-search-card__salary"))
        if salary_el:
            job["salary"] = salary_el.get_text(strip=True)

        # Job URL
        link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
        if not link_el:
            link_el = card.find("a", href=re.compile(r"/jobs/view/"))
        if link_el:
            href = link_el.get("href", "")
            if isinstance(href, str):
                job["url"] = href.split("?")[0]
        else:
            job["url"] = f"https://www.linkedin.com/jobs/view/{job['jobId']}"

        return job

    # --- Job Detail Enrichment ---

    async def _enrich_with_details(self, job: dict[str, Any]) -> dict[str, Any]:
        """Fetch the full job detail page and extract additional fields."""
        job_id = job.get("jobId", "")
        if not job_id:
            return job

        detail_url = f"{GUEST_JOB_DETAIL_URL}/{job_id}"
        html = await fetch_html(self.client, detail_url, self.rate_limiter,
                                api_request=True, proxy_config=self.proxy_config,
                                byte_budget=self.byte_budget)

        if not html:
            logger.warning(f"Failed to fetch details for job {job_id}")
            return job

        soup = BeautifulSoup(html, "lxml")

        # 1. JSON-LD structured data (most reliable — schema.org JobPosting)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            # Salary from structured data
            if not job.get("salary"):
                salary_data = json_ld.get("baseSalary", {})
                if salary_data:
                    val = salary_data.get("value", {})
                    min_v = val.get("minValue")
                    max_v = val.get("maxValue")
                    currency = salary_data.get("currency", "USD")
                    unit = val.get("unitText", "YEAR")
                    if min_v and max_v:
                        job["salary"] = f"{currency} {int(min_v):,} - {int(max_v):,} / {unit}"
                    elif min_v:
                        job["salary"] = f"{currency} {int(min_v):,}+ / {unit}"

        # 2. Description — both plain text and HTML
        desc_section = soup.find("div", class_=re.compile(r"show-more-less-html__markup"))
        if desc_section:
            job["description"] = desc_section.get_text(separator="\n", strip=True)
            job["descriptionHtml"] = str(desc_section)

        # 3. Salary fallback from page HTML. Use a space separator so the label and
        # value don't glue together, then strip the leading label.
        if not job.get("salary"):
            salary_el = soup.find("div", class_=re.compile(r"salary"))
            if salary_el:
                salary_text = salary_el.get_text(" ", strip=True)
                salary_text = re.sub(
                    r"^(Base pay range|Base salary|Compensation|Salary|Pay range)\s*[:\-]?\s*",
                    "", salary_text, flags=re.IGNORECASE,
                )
                job["salary"] = salary_text.strip()

        # 4. Job criteria list (seniority, type, function, industries)
        criteria_list = soup.find("ul", class_=re.compile(r"description__job-criteria-list"))
        if criteria_list:
            for item in criteria_list.find_all("li"):
                if not isinstance(item, Tag):
                    continue
                header = item.find("h3")
                value = item.find("span", class_=re.compile(r"description__job-criteria-text"))
                if header and value:
                    header_text = header.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)
                    if "seniority" in header_text:
                        job["seniorityLevel"] = value_text
                    elif "employment" in header_text or "type" in header_text:
                        job["employmentType"] = value_text
                    elif "function" in header_text:
                        job["jobFunction"] = value_text
                    elif "industr" in header_text:
                        job["industries"] = value_text

        # 5. Applicant count
        applicant_el = soup.find("figcaption", class_=re.compile(r"num-applicants"))
        if not applicant_el:
            applicant_el = soup.find("span", class_=re.compile(r"num-applicants"))
        if applicant_el:
            job["applicantCount"] = applicant_el.get_text(strip=True)

        # 6. Company info embedded in the detail page (free — no extra request)
        company_info = self._extract_company_from_detail(soup)
        for key, val in company_info.items():
            if not job.get(key):
                job[key] = val

        return job

    def _extract_json_ld(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract schema.org JSON-LD structured data from page."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.get_text())
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    return data
            except (json.JSONDecodeError, AttributeError):
                continue
        return {}

    def _extract_company_from_detail(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract company size and industry embedded in the job detail page.

        LinkedIn includes a company info panel on detail pages — no extra
        HTTP request needed.
        """
        result: dict[str, Any] = {}

        # Company info list items (employee count, industry)
        info_items = soup.find_all(
            class_=re.compile(r"jobs-company__list-item|company-list-item|org-top-card-summary-info-list__info-item")
        )
        for item in info_items:
            if not isinstance(item, Tag):
                continue
            text = item.get_text(strip=True)
            if "employee" in text.lower():
                result["companyEmployeeCount"] = text
            elif not result.get("companyIndustry") and len(text) > 3:
                result["companyIndustry"] = text

        # Company logo from detail page
        logo_el = soup.find("img", class_=re.compile(r"jobs-company__logo|company-logo|artdeco-entity-image"))
        if logo_el:
            src = logo_el.get("src", "")
            if isinstance(src, str) and src.startswith("http"):
                result["companyLogoUrl"] = src

        return result
