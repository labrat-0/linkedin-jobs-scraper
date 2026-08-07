# Track Director Openings at Companies You're Watching

**Task title (paste into Console):** Track Director Openings at Companies You're Watching

**Task description (paste into Console):** Monitor Director-level roles at a named list of companies on LinkedIn. See who is building out leadership at competitors or target accounts, with full details.

**Slug:** `exec-openings-target-companies` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** Executive recruiters, competitive intelligence

**Typical input:**

```json
{
  "keywordsList": ["Stripe", "Plaid", "Brex", "Marqeta", "Adyen"],
  "location": "United States",
  "companyFilter": ["stripe", "plaid", "brex", "marqeta", "adyen"],
  "experienceLevel": "5",
  "fetchJobDetails": true,
  "maxResultsPerSearch": 100,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

Two things to know about targeting companies:

- Put each **company name in `keywordsList`** so LinkedIn surfaces that
  company's jobs, then list the same names in `companyFilter` to clean out
  look-alikes. `companyFilter` on its own is a post-filter and will not
  reliably reach a specific company in a broad role search.
- `companyFilter` matches by substring, so prefer **distinctive company
  names**. Short or common names over-match (for example "ramp" also
  catches "Rampart Aviation", "mercury" catches "Mercury Insurance").
- `experienceLevel: "5"` is Director. Use `"6"` for Executive, or drop the
  field to include all seniority levels at those companies.
- **Seniority is verified per job, not filtered by LinkedIn.** LinkedIn ignores
  the seniority filter for logged-out clients, so the actor checks each job's
  published "Seniority level" itself. That requires `fetchJobDetails` (switched
  on automatically) and means every returned row genuinely says Director.
  LinkedIn publishes no seniority on roughly half of postings, and those rows
  are dropped rather than guessed at — expect noticeably fewer results than
  `maxResultsPerSearch`, with the run summary reporting how many were dropped
  and why.

**Returns:** listing fields on every row (`jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`). Because
`fetchJobDetails: true`, each row also includes `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, `applicantCount`, plus `companyIndustry` when LinkedIn shows it.

_Validated on-platform (build 0.0.34): every returned row carries a published
`seniorityLevel` of Director — verified client-side, since LinkedIn ignores the
seniority filter itself. Expect a modest row count: in a control run, 53 of 69
candidate jobs had no published seniority and were dropped rather than guessed
at. The run summary reports that split every time._
