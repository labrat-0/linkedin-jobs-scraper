"""Pydantic models for LinkedIn Jobs Scraper input validation and output formatting."""

from __future__ import annotations

import itertools
from typing import Any

from pydantic import BaseModel


# --- Input Model ---


class ScraperInput(BaseModel):
    """Validated scraper input from Apify."""

    # Single search (backward compatible)
    keywords: str = ""
    location: str = ""
    geo_id: str = ""

    # Batch search — overrides single keywords/location when provided
    keywords_list: list[str] = []
    locations_list: list[str] = []

    # Filters
    #
    # Only datePosted is a real LinkedIn-side filter. Measured against an
    # unfiltered baseline, the guest endpoints honour f_TPR and silently ignore
    # f_WT, f_E, f_JT and f_SB2 — f_WT=1/2/3 return byte-identical result sets.
    # jobType and experienceLevel are therefore enforced client-side against the
    # detail-page criteria list; workType and salary were removed outright since
    # nothing in the logged-out markup can back them.
    date_posted: str = ""
    job_type: str = ""
    experience_level: str = ""
    company_filter: list[str] = []  # filter results by company name or LinkedIn slug
    title_only: bool = False  # when True, keep only jobs where keyword appears in title

    # Scraper settings
    fetch_job_details: bool = False
    # Extra opt-in: fetch each company's public page for companyEmployeeCount.
    # Adds one request per UNIQUE company (cached) — gated separately from
    # fetch_job_details because company pages are large and proxy-costly.
    fetch_company_details: bool = False
    max_results: int = 100
    max_results_per_search: int = 100  # per keyword/location combo in batch mode

    @classmethod
    def from_actor_input(cls, raw: dict[str, Any]) -> ScraperInput:
        """Map Apify input schema field names to model field names."""
        return cls(
            keywords=raw.get("keywords", ""),
            location=raw.get("location", ""),
            geo_id=raw.get("geoId", ""),
            keywords_list=raw.get("keywordsList", []),
            locations_list=raw.get("locationsList", []),
            date_posted=raw.get("datePosted", ""),
            job_type=raw.get("jobType", ""),
            experience_level=raw.get("experienceLevel", ""),
            company_filter=raw.get("companyFilter", []),
            title_only=raw.get("titleOnly", False),
            fetch_job_details=raw.get("fetchJobDetails", False),
            fetch_company_details=raw.get("fetchCompanyDetails", False),
            max_results=raw.get("maxResults", 100),
            max_results_per_search=raw.get("maxResultsPerSearch", 100),
        )

    def validate_input(self) -> str | None:
        """Return an error message if input is invalid."""
        has_keywords = self.keywords or self.keywords_list
        has_location = self.location or self.locations_list
        if not has_keywords and not has_location:
            return (
                "At least one search parameter is required: "
                "'keywords', 'keywordsList', 'location', or 'locationsList'."
            )
        return None

    def get_search_combos(self) -> list[tuple[str, str]]:
        """Return all (keyword, location) pairs for batch search.

        If keywordsList/locationsList are provided, runs all combinations.
        Falls back to single keywords/location for backward compatibility.
        """
        kws = self.keywords_list if self.keywords_list else ([self.keywords] if self.keywords else [""])
        locs = self.locations_list if self.locations_list else ([self.location] if self.location else [""])
        return list(itertools.product(kws, locs))

    def build_search_params(self, keywords: str = "", location: str = "") -> dict[str, str]:
        """Build LinkedIn search URL parameters.

        Args:
            keywords: Override keywords for this specific search combo.
            location: Override location for this specific search combo.
        """
        params: dict[str, str] = {}

        kw = keywords or self.keywords
        loc = location or self.location

        if kw:
            params["keywords"] = kw
        if loc:
            params["location"] = loc
        if self.geo_id:
            params["geoId"] = self.geo_id

        # Date posted filter
        date_map = {
            "past_24_hours": "r86400",
            "past_week": "r604800",
            "past_month": "r2592000",
        }
        if self.date_posted and self.date_posted in date_map:
            params["f_TPR"] = date_map[self.date_posted]

        # f_JT / f_E are deliberately NOT sent. LinkedIn's guest endpoints accept
        # and discard them, so sending them buys nothing but an extra query param
        # for the bot fingerprint. jobType and experienceLevel are applied in
        # LinkedInJobsScraper._detail_filter_verdict instead.

        return params

    def has_detail_filters(self) -> bool:
        """True when a filter is active that can only be checked on the detail page."""
        return bool(self.job_type or self.experience_level)

    def batch_shortfall(self, combos: int) -> tuple[int, int] | None:
        """Report whether max_results is too low to run every search combination.

        max_results caps the run as a whole while max_results_per_search caps
        each combo, so a batch needs combos x per_search to finish. When it is
        short the run simply stops mid-way and the remaining combos never
        execute — silently, which is how published examples ended up covering
        two of four cities.

        Returns (combos_that_will_not_run, max_results_needed), or None when the
        configuration already covers the batch. Pure so it can be tested without
        the Actor SDK.
        """
        if combos <= 1:
            return None
        needed = combos * self.max_results_per_search
        if self.max_results >= needed:
            return None
        # Combos are walked in order, so whole combos beyond this many are the
        # ones that never start.
        combos_that_run = self.max_results // self.max_results_per_search
        return combos - combos_that_run, needed


# --- Client-side filter vocabularies ---
#
# LinkedIn prints these exact strings in the detail page's job-criteria list, so
# they are what the enum codes have to be compared against. Keys mirror the
# enum / enumTitles pairs in .actor/input_schema.json.

JOB_TYPE_LABELS = {
    "F": "Full-time",
    "P": "Part-time",
    "C": "Contract",
    "T": "Temporary",
    "V": "Volunteer",
    "I": "Internship",
    "O": "Other",
}

EXPERIENCE_LEVEL_LABELS = {
    "1": "Internship",
    "2": "Entry level",
    "3": "Associate",
    "4": "Mid-Senior level",
    "5": "Director",
    "6": "Executive",
}

# LinkedIn's placeholder when an employer published no seniority. Roughly half of
# postings carry it, so it is a distinct outcome from "does not match" and is
# counted separately.
SENIORITY_UNPUBLISHED = "Not Applicable"


# --- Output Formatting ---


def format_job_card(data: dict[str, Any]) -> dict[str, Any]:
    """Format a job card into clean, consistent output schema."""
    return {
        # Core job info
        "jobId": data.get("jobId", ""),
        "title": data.get("title", ""),
        "company": data.get("company", ""),
        "companyUrl": data.get("companyUrl", ""),
        "location": data.get("location", ""),
        "postedDate": data.get("postedDate", ""),
        "postedDateTimestamp": data.get("postedDateTimestamp", ""),
        "salary": data.get("salary", ""),
        "url": data.get("url", ""),

        # Batch tracking — which search query produced this result
        "searchKeywords": data.get("searchKeywords", ""),
        "searchLocation": data.get("searchLocation", ""),

        # Full job details (when fetchJobDetails = true)
        "description": data.get("description", ""),
        "descriptionHtml": data.get("descriptionHtml", ""),
        "seniorityLevel": data.get("seniorityLevel", ""),
        "employmentType": data.get("employmentType", ""),
        "jobFunction": data.get("jobFunction", ""),
        "industries": data.get("industries", ""),
        "applicantCount": data.get("applicantCount", ""),

        # Company enrichment
        # companyIndustry: from job detail criteria (fetchJobDetails)
        # companyEmployeeCount: from company page (fetchCompanyDetails)
        "companyEmployeeCount": data.get("companyEmployeeCount", ""),
        "companyIndustry": data.get("companyIndustry", ""),
    }
