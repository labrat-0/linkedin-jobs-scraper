# Build a Weekly Nursing Job Feed for Any US Metro

**Task title (paste into Console):** Build a Weekly Nursing Job Feed for Any US Metro

**Task description (paste into Console):** Scrape registered nurse and nurse practitioner roles across major US metros, refreshed weekly and tagged by city. Built for healthcare staffing and recruiters.

**Slug:** `healthcare-nursing-by-metro` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** Healthcare staffing agencies

**Typical input:**

```json
{
  "keywordsList": ["registered nurse", "nurse practitioner"],
  "locationsList": [
    "New York, NY",
    "Los Angeles, CA",
    "Chicago, IL",
    "Houston, TX"
  ],
  "datePosted": "past_week",
  "maxResults": 400,
  "maxResultsPerSearch": 50,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**Returns:** listing fields on every row: `jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`. Runs listing-only. Set
`fetchJobDetails: true` to add `description`, `descriptionHtml`,
`seniorityLevel`, `employmentType`, `jobFunction`, `industries`, and
`applicantCount`.

**Set `maxResults` to cover the whole batch.** It caps the run as a whole, so
leaving it at the default 100 stops the run after two metros. 8 searches x 50 = 400.

_Validated on-platform (build 0.0.35): 400 rows, all 8 keyword x metro
combinations covered, 100 per metro, 400 unique jobIds, every row tagged with
its search city._
