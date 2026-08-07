# Scrape Remote Software Engineer Jobs Posted Today (US)

**Task title (paste into Console):** Scrape Remote Software Engineer Jobs Posted Today (US)

**Task description (paste into Console):** Pull software engineer roles advertised as remote on LinkedIn in the last 24 hours across the US. No login or API key. Run it daily for a fresh jobs feed.

**Slug:** `remote-swe-us-24h` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** Job seekers, job boards, aggregators

**Typical input:**

```json
{
  "keywords": "remote software engineer",
  "location": "United States",
  "datePosted": "past_24_hours",
  "maxResults": 100,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**How "remote" is targeted here:** through the search text, not a filter.
LinkedIn accepts a work-arrangement filter from logged-out clients and then
ignores it — on-site, remote and hybrid searches return byte-identical results
— and publishes no per-job remote/hybrid/on-site value outside its logged-in
UI. So "remote" in the keywords is a text match against how the posting is
written, and some hybrid roles will come through. For a stronger signal, set
`fetchJobDetails: true` and post-filter `description` for "hybrid" or "days in
office".

**Returns:** listing fields on every row: `jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`. Runs listing-only for speed
and low cost. Set `fetchJobDetails: true` to also get `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, and `applicantCount`.

_Validated on-platform: 25 rows, all posted within 24 hours._
