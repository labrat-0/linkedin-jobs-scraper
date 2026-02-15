"""Pydantic models for LinkedIn Jobs Scraper input validation and output formatting."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# --- Input Model ---


class ScraperInput(BaseModel):
    """Validated scraper input from Apify."""

    keywords: str = ""
    location: str = ""
    geo_id: str = ""
    date_posted: str = ""
    job_type: str = ""
    experience_level: str = ""
    work_type: str = ""
    salary: str = ""
    fetch_job_details: bool = True
    max_results: int = 100

    @classmethod
    def from_actor_input(cls, raw: dict[str, Any]) -> ScraperInput:
        """Map Apify input schema field names to model field names."""
        return cls(
            keywords=raw.get("keywords", ""),
            location=raw.get("location", ""),
            geo_id=raw.get("geoId", ""),
            date_posted=raw.get("datePosted", ""),
            job_type=raw.get("jobType", ""),
            experience_level=raw.get("experienceLevel", ""),
            work_type=raw.get("workType", ""),
            salary=raw.get("salary", ""),
            fetch_job_details=raw.get("fetchJobDetails", True),
            max_results=raw.get("maxResults", 100),
        )

    def validate_input(self) -> str | None:
        """Return an error message if input is invalid."""
        if not self.keywords and not self.location:
            return "At least one of 'keywords' or 'location' is required."
        return None

    def build_search_params(self) -> dict[str, str]:
        """Build LinkedIn search URL parameters from input."""
        params: dict[str, str] = {}

        if self.keywords:
            params["keywords"] = self.keywords
        if self.location:
            params["location"] = self.location
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

        # Job type filter
        if self.job_type:
            params["f_JT"] = self.job_type

        # Experience level filter
        if self.experience_level:
            params["f_E"] = self.experience_level

        # Work type filter (on-site/remote/hybrid)
        if self.work_type:
            params["f_WT"] = self.work_type

        # Salary filter
        if self.salary:
            params["f_SB2"] = self.salary

        return params


# --- Output Formatting ---


def format_job_card(data: dict[str, Any]) -> dict[str, Any]:
    """Format a job card from search results into clean output.

    This is the basic data extracted from search result cards.
    """
    return {
        "jobId": data.get("jobId", ""),
        "title": data.get("title", ""),
        "company": data.get("company", ""),
        "companyUrl": data.get("companyUrl", ""),
        "location": data.get("location", ""),
        "postedDate": data.get("postedDate", ""),
        "postedDateTimestamp": data.get("postedDateTimestamp", ""),
        "salary": data.get("salary", ""),
        "url": data.get("url", ""),
        # Detail fields -- populated when fetchJobDetails is true
        "description": data.get("description", ""),
        "seniorityLevel": data.get("seniorityLevel", ""),
        "employmentType": data.get("employmentType", ""),
        "jobFunction": data.get("jobFunction", ""),
        "industries": data.get("industries", ""),
        "applicantCount": data.get("applicantCount", ""),
    }
