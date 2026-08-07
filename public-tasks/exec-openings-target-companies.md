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

**Returns:** listing fields on every row (`jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`, `workplaceType`). Because
`fetchJobDetails: true`, each row also includes `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, `applicantCount`, plus `companyIndustry` when LinkedIn shows it.
`workplaceType` is empty here because no Work Arrangement filter is applied.

_Validated on-platform: 29 Director-level rows across the target companies, no false matches._
