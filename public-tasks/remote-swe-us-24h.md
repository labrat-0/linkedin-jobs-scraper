# Scrape Remote Software Engineer Jobs Posted Today (US)

**Task title (paste into Console):** Scrape Remote Software Engineer Jobs Posted Today (US)

**Task description (paste into Console):** Pull remote software engineer roles posted on LinkedIn in the last 24 hours across the US. No login or API key. Run it daily for a fresh jobs feed.

**Slug:** `remote-swe-us-24h` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** Job seekers, job boards, aggregators

**Typical input:**

```json
{
  "keywords": "software engineer",
  "location": "United States",
  "workType": "2",
  "datePosted": "past_24_hours",
  "maxResults": 100,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**Returns:** listing fields on every row: `jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`, and `workplaceType` (set here
because a Work Arrangement filter is applied). Runs listing-only for speed
and low cost. Set `fetchJobDetails: true` to also get `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, and `applicantCount`.

_Validated on-platform: 25/25 rows remote, all posted within 24 hours._
