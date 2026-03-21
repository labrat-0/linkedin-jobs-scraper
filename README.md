# LinkedIn Jobs Scraper

Scrape LinkedIn job listings at scale. **No API key. No login. No browser. No cookies.** Pure HTTP — fast, cheap, and reliable. Built for AI agents, lead generation pipelines, and job market research.

---

## What it does

This actor scrapes job listings from LinkedIn's public job search pages and returns clean, structured JSON. It supports single searches, batch searches across multiple keywords and locations in one run, and optional company enrichment for lead generation.

**Key data extracted:**
- Job title, company, location, posted date, salary
- Full job description (plain text + HTML)
- Required skills (structured list)
- Seniority level, employment type, job function, industries
- Applicant count
- Recruiter / hiring manager name, title, and LinkedIn profile URL
- Company size (employee count), industry, logo
- Company website and description (with extended enrichment enabled)

---

## What's new

### Batch Search
Run multiple keywords and locations in a single actor run. Use `keywordsList` and `locationsList` — the actor runs all combinations automatically and deduplicates results.

**Example:** `['python developer', 'data engineer'] × ['New York', 'Remote']` = 4 searches, one run.

### Skills Extraction
Extracts required skills from the job detail page into a structured list — not buried in the description. Ready for filtering, scoring, and agent use.

```json
"skills": ["Python", "SQL", "dbt", "Spark", "AWS"]
```

### Recruiter / Hiring Manager Info
When LinkedIn shows who posted the job, the actor extracts their name, title, and profile URL. Direct outreach fuel for sales and recruitment teams.

```json
"recruiterName": "Jane Smith",
"recruiterTitle": "Senior Technical Recruiter",
"recruiterProfileUrl": "https://www.linkedin.com/in/jane-smith"
```

### Company Filter
Only want jobs from specific companies? Pass a list of company names or LinkedIn slugs and the actor filters automatically — no post-processing needed.

### Company Enrichment
Enable `fetchCompanyDetails` to pull the company's LinkedIn page for their website URL and company description. Results are cached per company within the run — one company, one extra request, no matter how many jobs they have.

### Description HTML
Both plain text and raw HTML of the job description are now included in the output — useful for agents that need to parse or render the content.

---

## Use cases

### Lead Generation
Turn LinkedIn hiring activity into a prospect pipeline:
- Find companies actively hiring in your target space
- Extract recruiter names and profile URLs for direct outreach
- Use company employee count and industry to qualify leads
- Feed into Clay, HubSpot, or Salesforce via Apify integrations

### AI Agent Integration (MCP)
Use this actor as a live data source for AI agents:
- Search LinkedIn jobs in real time from Claude, GPT, or any MCP-compatible agent
- Pull structured skills data for matching, gap analysis, or market research
- Batch search multiple roles and locations from a single agent prompt
- No authentication required — works out of the box with Apify's hosted MCP server

### Job Market Research
- Track hiring trends across roles, locations, and industries
- Monitor which companies are expanding (by volume of postings)
- Analyze salary ranges and experience requirements over time
- Extract required skills to understand what the market actually wants

### Recruitment & Talent Intelligence
- Build sourcing pipelines across multiple job titles and cities at once
- Identify which companies are hiring for specific skill sets
- Track applicant counts to gauge competition for specific roles

---

## Key features

- **No API key, login, or cookies** — scrapes public pages only
- **No browser / no Playwright** — pure HTTP, lower cost, faster execution
- **Batch search** — multiple keywords × locations in one run
- **Skills extraction** — structured list from each job detail page
- **Recruiter info** — name, title, LinkedIn profile URL when available
- **Company enrichment** — employee count, industry, website (optional deeper fetch)
- **Description HTML** — raw HTML alongside plain text
- **Deduplication** — jobId-based dedup across all batch searches
- **Company filter** — whitelist specific companies by name or slug
- **MCP-ready** — works as an AI agent tool via Apify's hosted MCP server
- **Resume on migration** — Apify state survives actor migrations mid-run

---

## Output format

Each job returns a JSON object:

```json
{
  "jobId": "3812345678",
  "title": "Senior Data Engineer",
  "company": "Stripe",
  "companyUrl": "https://www.linkedin.com/company/stripe",
  "location": "San Francisco, CA",
  "postedDate": "2 days ago",
  "postedDateTimestamp": "2026-03-18",
  "salary": "USD 180,000 - 240,000 / YEAR",
  "url": "https://www.linkedin.com/jobs/view/3812345678",

  "searchKeywords": "data engineer",
  "searchLocation": "United States",

  "description": "We are looking for a Senior Data Engineer...",
  "descriptionHtml": "<div class=\"show-more-less-html__markup\">...</div>",
  "skills": ["Python", "SQL", "Spark", "dbt", "AWS", "Airflow"],
  "seniorityLevel": "Mid-Senior level",
  "employmentType": "Full-time",
  "jobFunction": "Engineering and Information Technology",
  "industries": "Financial Services",
  "applicantCount": "Over 200 applicants",

  "recruiterName": "Jane Smith",
  "recruiterTitle": "Senior Technical Recruiter",
  "recruiterProfileUrl": "https://www.linkedin.com/in/jane-smith",

  "companyEmployeeCount": "1,001-5,000 employees",
  "companyIndustry": "Financial Services",
  "companyLogoUrl": "https://media.licdn.com/dms/image/...",

  "companyWebsite": "https://stripe.com",
  "companyDescription": "Stripe is a financial infrastructure platform..."
}
```

Fields `descriptionHtml`, `skills`, `recruiterName`, `recruiterTitle`, `recruiterProfileUrl`, `companyEmployeeCount`, `companyIndustry` require `fetchJobDetails: true`.

Fields `companyWebsite` and `companyDescription` require `fetchCompanyDetails: true`.

---

## Input reference

| Field | Type | Default | Description |
|---|---|---|---|
| `keywords` | string | — | Single keyword search |
| `location` | string | — | Single location search |
| `keywordsList` | string[] | — | Batch keywords (overrides `keywords`) |
| `locationsList` | string[] | — | Batch locations (overrides `location`) |
| `geoId` | string | — | LinkedIn geo ID for precise location |
| `companyFilter` | string[] | — | Whitelist companies by name or slug |
| `datePosted` | select | any | `past_24_hours`, `past_week`, `past_month` |
| `jobType` | select | any | Full-time, Part-time, Contract, etc. |
| `experienceLevel` | select | any | Entry, Associate, Mid-Senior, Director, etc. |
| `workType` | select | any | On-site, Remote, Hybrid |
| `salary` | select | any | Minimum salary filter (USD) |
| `fetchJobDetails` | boolean | `true` | Load full detail page per job |
| `fetchCompanyDetails` | boolean | `false` | Load company page for website + description |
| `maxResults` | integer | 100 | Total result cap across all searches |
| `maxResultsPerSearch` | integer | 100 | Cap per keyword/location combo (batch mode) |
| `proxyConfiguration` | object | RESIDENTIAL | Proxy settings — residential recommended |

---

## Batch search example

Search for three roles across two cities in one run:

```json
{
  "keywordsList": ["python developer", "data engineer", "ML engineer"],
  "locationsList": ["New York, NY", "San Francisco, CA"],
  "datePosted": "past_week",
  "workType": "2",
  "fetchJobDetails": true,
  "maxResultsPerSearch": 50
}
```

This runs 6 searches (3 × 2), returns up to 300 jobs, deduplicates, and tags each result with `searchKeywords` and `searchLocation` so you know which combo found it.

---

## Lead generation example

Find hiring decision-makers at fintech companies:

```json
{
  "keywordsList": ["engineering manager", "vp engineering", "head of engineering"],
  "locationsList": ["United States"],
  "companyFilter": ["stripe", "plaid", "brex", "ramp", "mercury"],
  "fetchJobDetails": true,
  "fetchCompanyDetails": true,
  "maxResultsPerSearch": 100
}
```

Output includes recruiter names, company websites, employee counts — ready to pipe into your CRM.

---

## MCP Integration

Use this actor as a real-time tool for AI agents — no custom MCP server needed.

- **Endpoint:** `https://mcp.apify.com?tools=labrat011/linkedin-jobs-scraper`
- **Auth:** `Authorization: Bearer <APIFY_TOKEN>`
- **Transport:** Streamable HTTP
- **Compatible with:** Claude Desktop, Cursor, VS Code, Windsurf, Warp, Gemini CLI

**Claude Desktop / Cursor config:**

```json
{
  "mcpServers": {
    "linkedin-jobs-scraper": {
      "url": "https://mcp.apify.com?tools=labrat011/linkedin-jobs-scraper",
      "headers": {
        "Authorization": "Bearer <APIFY_TOKEN>"
      }
    }
  }
}
```

Once connected, your AI agent can search LinkedIn jobs, extract skills, track hiring trends, and pull recruiter info — all from a natural language prompt.

---

## Proxy guidance

LinkedIn aggressively blocks datacenter IPs. **Residential proxies are strongly recommended.** The actor defaults to Apify's RESIDENTIAL proxy group.

Without proxies, expect frequent 403 errors and low success rates. With residential proxies, the actor reliably handles large batch runs.

---

## Limitations

- LinkedIn caps search pagination at 1,000 results per query — use multiple searches or tighter filters to go deeper
- Recruiter info is only shown by LinkedIn when the poster makes it public — not available on every job
- Salary data is only present when LinkedIn displays it on the listing
- Skills extraction depends on LinkedIn including a skills section on the job detail page
- Company page enrichment requires an additional request per unique company — enable only when needed
