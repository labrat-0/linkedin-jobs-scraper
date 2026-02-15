"""Core LinkedIn Jobs scraping logic. HTML parsing of public job search pages."""

from __future__ import annotations

import logging
import re
from typing import Any, AsyncIterator

import httpx
from bs4 import BeautifulSoup, Tag

from .models import ScraperInput, format_job_card
from .utils import BASE_URL, GUEST_API_URL, RateLimiter, fetch_html

logger = logging.getLogger(__name__)


class LinkedInJobsScraper:
    """Scrapes LinkedIn Jobs using public HTML pages (no auth required)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: RateLimiter,
        config: ScraperInput,
    ) -> None:
        self.client = client
        self.rate_limiter = rate_limiter
        self.config = config

    async def scrape(self) -> AsyncIterator[dict[str, Any]]:
        """Main entry point -- scrape job listings from LinkedIn search."""
        params = self.config.build_search_params()
        count = 0
        max_results = self.config.max_results

        # First page: use the main search URL to get total results count
        search_url = f"{BASE_URL}/jobs/search"
        logger.info(f"Starting LinkedIn job search: {params}")

        first_page_html = await fetch_html(
            self.client, search_url, self.rate_limiter, params
        )

        if not first_page_html:
            logger.error("Failed to fetch first search page")
            return

        # Parse total results count from first page
        total_results = self._parse_total_results(first_page_html)
        if total_results is not None:
            logger.info(f"Total results available: {total_results}")
        else:
            logger.info("Could not determine total results count")

        # Parse job cards from first page (25 results)
        first_page_jobs = self._parse_search_cards(first_page_html)
        logger.info(f"First page: found {len(first_page_jobs)} job cards")

        for job in first_page_jobs:
            if count >= max_results:
                return

            if self.config.fetch_job_details:
                job = await self._enrich_with_details(job)

            yield format_job_card(job)
            count += 1

        # Paginate using the guest API (10 results per page, start=25,35,45...)
        # LinkedIn caps at start=990 (returns 400 at start=1000)
        start = 25  # first page already gave us 0-24

        while count < max_results:
            if start >= 1000:
                logger.info("Reached LinkedIn pagination limit (start=1000)")
                break

            if total_results is not None and start >= total_results:
                logger.info("Reached end of available results")
                break

            page_params = dict(params)
            page_params["start"] = str(start)

            page_html = await fetch_html(
                self.client, GUEST_API_URL, self.rate_limiter, page_params
            )

            if not page_html:
                logger.info(f"No more results at start={start}")
                break

            page_jobs = self._parse_search_cards(page_html)
            if not page_jobs:
                logger.info(f"No job cards found at start={start}")
                break

            logger.info(f"Page start={start}: found {len(page_jobs)} job cards")

            for job in page_jobs:
                if count >= max_results:
                    return

                if self.config.fetch_job_details:
                    job = await self._enrich_with_details(job)

                yield format_job_card(job)
                count += 1

            start += 10  # guest API returns 10 per page

    # --- HTML Parsing ---

    def _parse_total_results(self, html: str) -> int | None:
        """Extract total results count from search page HTML.

        LinkedIn hides total count in: <code id="totalResults">1234</code>
        or in a <span> with text like "1,234 results"
        """
        soup = BeautifulSoup(html, "lxml")

        # Method 1: hidden <code> element
        code_el = soup.find("code", id="totalResults")
        if code_el:
            try:
                return int(code_el.get_text(strip=True).replace(",", ""))
            except (ValueError, TypeError):
                pass

        # Method 2: results count in page text
        results_div = soup.find("div", class_="results-context-header")
        if results_div:
            text = results_div.get_text(strip=True)
            match = re.search(r"([\d,]+)\s+results?", text)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Method 3: subtitle with count
        subtitle = soup.find("span", class_="results-context-header__job-count")
        if subtitle:
            try:
                return int(subtitle.get_text(strip=True).replace(",", "").replace("+", ""))
            except (ValueError, TypeError):
                pass

        return None

    def _parse_search_cards(self, html: str) -> list[dict[str, Any]]:
        """Parse job cards from search results HTML.

        Each job card is a <div class="job-search-card" data-entity-urn="urn:li:jobPosting:{id}">
        """
        soup = BeautifulSoup(html, "lxml")
        jobs: list[dict[str, Any]] = []

        # Find all job cards
        cards = soup.find_all("div", class_="job-search-card")

        # Fallback: sometimes the class varies
        if not cards:
            cards = soup.find_all("li")
            cards = [
                c for c in cards
                if isinstance(c, Tag)
                and c.find("div", attrs={"data-entity-urn": True})
            ]
            # Unwrap to the inner div
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
            # Try to find it in a child element
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
            # Company URL
            company_link = company_el.find("a")
            if company_link:
                href = company_link.get("href", "")
                if isinstance(href, str):
                    job["companyUrl"] = href.split("?")[0]  # strip tracking params

        # Location
        location_el = card.find("span", class_=re.compile(r"job-search-card__location"))
        if location_el:
            job["location"] = location_el.get_text(strip=True)

        # Posted date
        time_el = card.find("time")
        if time_el:
            job["postedDateTimestamp"] = time_el.get("datetime", "")
            job["postedDate"] = time_el.get_text(strip=True)

        # Salary (sometimes shown on card)
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
                job["url"] = href.split("?")[0]  # strip tracking params
        else:
            # Construct URL from job ID
            job["url"] = f"https://www.linkedin.com/jobs/view/{job['jobId']}"

        return job

    async def _enrich_with_details(self, job: dict[str, Any]) -> dict[str, Any]:
        """Fetch the full job detail page and extract additional fields."""
        job_id = job.get("jobId", "")
        if not job_id:
            return job

        detail_url = f"{BASE_URL}/jobs/view/{job_id}"
        html = await fetch_html(self.client, detail_url, self.rate_limiter)

        if not html:
            logger.warning(f"Failed to fetch details for job {job_id}")
            return job

        soup = BeautifulSoup(html, "lxml")

        # Description
        desc_section = soup.find("div", class_=re.compile(r"show-more-less-html__markup"))
        if desc_section:
            job["description"] = desc_section.get_text(separator="\n", strip=True)

        # Salary from detail page (if not already present from card)
        if not job.get("salary"):
            salary_el = soup.find("div", class_=re.compile(r"salary"))
            if salary_el:
                job["salary"] = salary_el.get_text(strip=True)

        # Job criteria list (seniority, type, function, industries)
        criteria_list = soup.find("ul", class_=re.compile(r"description__job-criteria-list"))
        if criteria_list:
            criteria_items = criteria_list.find_all("li")
            for item in criteria_items:
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

        # Applicant count
        applicant_el = soup.find("figcaption", class_=re.compile(r"num-applicants"))
        if not applicant_el:
            applicant_el = soup.find("span", class_=re.compile(r"num-applicants"))
        if applicant_el:
            job["applicantCount"] = applicant_el.get_text(strip=True)

        return job
