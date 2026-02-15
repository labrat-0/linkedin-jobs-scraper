"""Local test script for LinkedIn Jobs Scraper.

Run with: python test_local.py
Requires: pip install httpx pydantic beautifulsoup4 lxml

Tests the scraper directly against live LinkedIn (no Apify SDK needed).
"""

import asyncio
import json
import logging
import sys

import httpx

# Add parent directory so we can import src
sys.path.insert(0, ".")

from src.models import ScraperInput, format_job_card
from src.scraper import LinkedInJobsScraper
from src.utils import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def test_search() -> None:
    """Test basic job search."""
    logger.info("=== Test: Basic job search ===")

    config = ScraperInput(
        keywords="python developer",
        location="United States",
        fetch_job_details=True,
        max_results=5,  # Small number for testing
    )

    async with httpx.AsyncClient() as client:
        rate_limiter = RateLimiter()
        scraper = LinkedInJobsScraper(client, rate_limiter, config)

        jobs = []
        async for job in scraper.scrape():
            jobs.append(job)
            logger.info(f"  [{len(jobs)}] {job.get('title', 'N/A')} at {job.get('company', 'N/A')}")
            if job.get("salary"):
                logger.info(f"       Salary: {job['salary']}")
            if job.get("seniorityLevel"):
                logger.info(f"       Seniority: {job['seniorityLevel']}")

        logger.info(f"Total jobs scraped: {len(jobs)}")

        if jobs:
            logger.info("\nFirst job (full JSON):")
            print(json.dumps(jobs[0], indent=2, ensure_ascii=False))

    return len(jobs) > 0


async def test_search_no_details() -> None:
    """Test search without fetching detail pages."""
    logger.info("\n=== Test: Search without details ===")

    config = ScraperInput(
        keywords="data engineer",
        location="Remote",
        fetch_job_details=False,
        max_results=5,
    )

    async with httpx.AsyncClient() as client:
        rate_limiter = RateLimiter()
        scraper = LinkedInJobsScraper(client, rate_limiter, config)

        jobs = []
        async for job in scraper.scrape():
            jobs.append(job)
            logger.info(f"  [{len(jobs)}] {job.get('title', 'N/A')} at {job.get('company', 'N/A')}")

        logger.info(f"Total jobs scraped: {len(jobs)}")

        # Verify detail fields are empty
        if jobs:
            assert jobs[0].get("description") == "", "Description should be empty without details"
            logger.info("Confirmed: detail fields are empty (as expected)")

    return len(jobs) > 0


async def test_filters() -> None:
    """Test search with filters applied."""
    logger.info("\n=== Test: Search with filters ===")

    config = ScraperInput(
        keywords="software engineer",
        location="San Francisco, CA",
        date_posted="past_week",
        job_type="F",  # Full-time
        experience_level="4",  # Mid-Senior
        work_type="2",  # Remote
        fetch_job_details=False,
        max_results=3,
    )

    params = config.build_search_params()
    logger.info(f"Search params: {params}")

    async with httpx.AsyncClient() as client:
        rate_limiter = RateLimiter()
        scraper = LinkedInJobsScraper(client, rate_limiter, config)

        jobs = []
        async for job in scraper.scrape():
            jobs.append(job)
            logger.info(f"  [{len(jobs)}] {job.get('title', 'N/A')} - {job.get('location', 'N/A')}")

        logger.info(f"Total jobs scraped: {len(jobs)}")

    return len(jobs) > 0


async def run_all_tests() -> None:
    """Run all tests."""
    results = {}

    try:
        results["basic_search"] = await test_search()
    except Exception as e:
        logger.error(f"Basic search test failed: {e}")
        results["basic_search"] = False

    try:
        results["no_details"] = await test_search_no_details()
    except Exception as e:
        logger.error(f"No details test failed: {e}")
        results["no_details"] = False

    try:
        results["filters"] = await test_filters()
    except Exception as e:
        logger.error(f"Filters test failed: {e}")
        results["filters"] = False

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST RESULTS:")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"  {name}: {status}")

    all_passed = all(results.values())
    logger.info(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
