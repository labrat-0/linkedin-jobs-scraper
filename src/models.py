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
    date_posted: str = ""
    job_type: str = ""
    experience_level: str = ""
    work_type: str = ""
    salary: str = ""
    company_filter: list[str] = []  # filter results by company name or LinkedIn slug

    # Scraper settings
    fetch_job_details: bool = False
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
            work_type=raw.get("workType", ""),
            salary=raw.get("salary", ""),
            company_filter=raw.get("companyFilter", []),
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

        if self.job_type:
            params["f_JT"] = self.job_type

        if self.experience_level:
            params["f_E"] = self.experience_level

        if self.work_type:
            params["f_WT"] = self.work_type

        if self.salary:
            params["f_SB2"] = self.salary

        return params


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
        "skills": data.get("skills", []),
        "seniorityLevel": data.get("seniorityLevel", ""),
        "employmentType": data.get("employmentType", ""),
        "jobFunction": data.get("jobFunction", ""),
        "industries": data.get("industries", ""),
        "applicantCount": data.get("applicantCount", ""),

        # Hiring manager / recruiter (when available on job page)
        "recruiterName": data.get("recruiterName", ""),
        "recruiterTitle": data.get("recruiterTitle", ""),
        "recruiterProfileUrl": data.get("recruiterProfileUrl", ""),

        # Company enrichment (from detail page — always when fetchJobDetails = true)
        "companyEmployeeCount": data.get("companyEmployeeCount", ""),
        "companyIndustry": data.get("companyIndustry", ""),
        "companyLogoUrl": data.get("companyLogoUrl", ""),

        # Extended company enrichment (when fetchCompanyDetails = true)
        "companyWebsite": data.get("companyWebsite", ""),
        "companyDescription": data.get("companyDescription", ""),
    }
