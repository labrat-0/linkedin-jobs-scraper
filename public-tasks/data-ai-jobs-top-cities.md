# Scrape Data and AI Jobs Across Top US Tech Cities

**Task title (paste into Console):** Scrape Data and AI Jobs Across Top US Tech Cities

**Task description (paste into Console):** Batch-search data engineer, data scientist, and ML engineer roles across New York, San Francisco, Austin, and Seattle in one run, tagged by city.

**Slug:** `data-ai-jobs-top-cities` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** Talent-market analysts, recruiters

**Typical input:**

```json
{
  "keywordsList": [
    "data engineer",
    "data scientist",
    "machine learning engineer"
  ],
  "locationsList": [
    "New York, NY",
    "San Francisco, CA",
    "Austin, TX",
    "Seattle, WA"
  ],
  "datePosted": "past_month",
  "maxResultsPerSearch": 50,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

This runs 12 searches (3 keywords x 4 locations) for up to 600 jobs,
deduplicated by `jobId`.

**Returns:** listing fields on every row: `jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`, and `workplaceType` (empty unless
you add a Work Arrangement filter). Runs listing-only to stay fast
across the batch. Set `fetchJobDetails: true` to add `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, and `applicantCount` (one extra request per job).

_Validated on-platform: 60 rows across the 12 searches, each tagged with its search city._
