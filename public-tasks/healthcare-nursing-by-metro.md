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
  "maxResultsPerSearch": 50,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**Returns:** listing fields on every row: `jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`, and `workplaceType` (empty unless
you add a Work Arrangement filter). Runs listing-only. Set
`fetchJobDetails: true` to add `description`, `descriptionHtml`,
`seniorityLevel`, `employmentType`, `jobFunction`, `industries`, and
`applicantCount`.

_Validated on-platform: 25 rows across the metros, each tagged with its search city._
