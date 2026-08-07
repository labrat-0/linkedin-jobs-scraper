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
  "maxResults": 150,
  "maxResultsPerSearch": 50,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**Set `maxResults` to cover the whole batch.** It caps the run as a whole, so
leaving it at the default 100 stops the run after two keywords and the third
never executes. 3 searches x 50 = 150.

**Returns:** listing fields on every row (`jobId`, `title`, `company`,
`companyUrl`, `location`, `postedDate`, `postedDateTimestamp`, `salary`,
`url`, `searchKeywords`, `searchLocation`). Because
`fetchJobDetails: true`, each row also includes `description`,
`descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`,
`industries`, `applicantCount`, plus `companyIndustry` when LinkedIn shows it.

_Validated on-platform (build 0.0.35): 150 rows, all 3 keyword searches covered,
150 unique jobIds. `employmentType` was present on 143 of 150. `seniorityLevel`
is thinner than it looks: 81 rows came back "Not Applicable" and 7 empty,
leaving 62 with a usable value — LinkedIn simply does not publish seniority for
most postings. Plan any seniority-based routing around that._
