# Find New Sales Roles Companies Are Hiring for This Week

**Task title (paste into Console):** Find New Sales Roles Companies Are Hiring for This Week

**Task description (paste into Console):** Surface new Account Executive, SDR, and BDR openings from the past week. A company staffing up sales has budget: turn it into a prospect list.

**Slug:** `saas-sales-roles-weekly` · **Actor:** `labrat011/linkedin-jobs-scraper` · **Audience:** B2B sales and revenue teams

**Typical input:**

```json
{
  "keywordsList": [
    "account executive",
    "sales development representative",
    "business development representative"
  ],
  "location": "United States",
  "datePosted": "past_week",
  "fetchJobDetails": true,
  "maxResultsPerSearch": 50,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**Returns:** listing fields on every row (`jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`). Because
`fetchJobDetails: true`, each row also includes `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, `applicantCount`, plus `companyIndustry` when LinkedIn shows it.

_Validated on-platform: 15 rows with seniority and employment-type fields populated._
