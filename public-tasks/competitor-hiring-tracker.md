# Monitor One Company's New Job Postings Every Week

**Task title (paste into Console):** Monitor One Company's New Job Postings Every Week

**Task description (paste into Console):** Track a single company's fresh LinkedIn postings each week. Read headcount growth by function and see where a competitor is investing before it's public.

**Slug:** `competitor-hiring-tracker` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** Competitive intelligence, strategy

**Typical input:**

```json
{
  "keywords": "Stripe",
  "location": "United States",
  "datePosted": "past_week",
  "companyFilter": ["stripe"],
  "maxResults": 100,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

How the company targeting works:

- The company **name goes in `keywords`** so LinkedIn surfaces that
  company's jobs, and `companyFilter` cleans out any look-alikes.
  `companyFilter` alone is a post-filter and will not reliably reach one
  company inside a broad search.
- `companyFilter` matches by substring, so this works best with a
  **distinctive company name**. A common word (for example "ramp" or
  "mercury") also matches unrelated firms, so tighten the filter or pick a
  more specific name if that happens.
- Some weeks a company posts little or nothing. A low or empty result is a
  real signal for a weekly monitor, not a failed run. Widen to
  `"past_month"` for a fuller baseline.

**Returns:** listing fields on every row: `jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`, and `workplaceType` (empty unless
you add a Work Arrangement filter). Runs listing-only for a fast
weekly diff. Set `fetchJobDetails: true` for `description`,
`seniorityLevel`, `employmentType`, `jobFunction`, `industries`,
`applicantCount`, and `fetchCompanyDetails: true` for
`companyEmployeeCount`.

_Validated on-platform: 25/25 rows from the target company, cleanly filtered._
