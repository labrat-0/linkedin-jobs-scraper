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
  "maxResults": 600,
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
`url`, `searchKeywords`, `searchLocation`. Runs listing-only to stay fast
across the batch. Set `fetchJobDetails: true` to add `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, and `applicantCount` (one extra request per job).

**Set `maxResults` to cover the whole batch.** It caps the run as a whole, so
leaving it at the default 100 stops the run after two combinations and the
remaining cities never execute. 12 searches x 50 = 600.

_Validated on-platform (build 0.0.35): 600 rows, all 12 keyword x city
combinations covered, 150 per city, 600 unique jobIds with no duplicates, every
row tagged with the search that found it._
