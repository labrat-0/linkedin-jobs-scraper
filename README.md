# LinkedIn Jobs Scraper

Scrape LinkedIn job listings at scale. **No API key. No login. No browser. No cookies.** Pure HTTP — fast, cheap, and reliable. Built for AI agents, lead generation pipelines, and job market research.

---

## What it does

This actor scrapes job listings from LinkedIn's public job search pages and returns clean, structured JSON. It supports single searches and batch searches across multiple keywords and locations in one run.

**Key data extracted:**
- Job title, company, location, posted date, salary
- Full job description (plain text + HTML)
- Seniority level, employment type, job function, industries
- Applicant count
- Company size (employee count), industry, logo (when shown on the job page)

---

## What's new

### ⚡ Faster runs — parallel pagination
Search pages are now fetched in concurrent batches instead of one at a time, cutting page-walk time **up to ~4x** on large or heavily-filtered searches. Same results, same order, same low cost — just faster. Smart early-stop still kicks in the moment a search is exhausted, so you never pay for pages you don't need.

### 🎯 Title-only filtering
Set `titleOnly: true` to keep only jobs whose **title** contains your keyword — perfect for precise role targeting (e.g. only actual "Product Analyst" titles, not every job that mentions "product" in the description). See the note in [Input reference](#input-reference) on using plain terms vs. Boolean syntax.

### Batch Search
Run multiple keywords and locations in a single actor run. Use `keywordsList` and `locationsList` — the actor runs all combinations automatically and deduplicates results.

**Example:** `['python developer', 'data engineer'] × ['New York', 'Remote']` = 4 searches, one run.

### Full Job Details
Enable `fetchJobDetails` to load each job's detail page and extract the full description (text + HTML), seniority level, employment type, job function, industry, applicant count, and salary when LinkedIn shows it.

### Company Filter
Only want jobs from specific companies? Pass a list of company names or LinkedIn slugs and the actor filters automatically — no post-processing needed.

### Description HTML
Both plain text and raw HTML of the job description are now included in the output — useful for agents that need to parse or render the content.

---

## Use cases

### Lead Generation
Turn LinkedIn hiring activity into a prospect pipeline:
- Find companies actively hiring in your target space
- Use company employee count and industry to qualify leads
- Feed into Clay, HubSpot, or Salesforce via Apify integrations

### AI Agent Integration (MCP)
Use this actor as a live data source for AI agents:
- Search LinkedIn jobs in real time from Claude, GPT, or any MCP-compatible agent
- Pull structured job data for matching, gap analysis, or market research
- Batch search multiple roles and locations from a single agent prompt
- No authentication required — works out of the box with Apify's hosted MCP server

### Job Market Research
- Track hiring trends across roles, locations, and industries
- Monitor which companies are expanding (by volume of postings)
- Analyze salary ranges and experience requirements over time
- Compare seniority and employment-type mix across markets

### Recruitment & Talent Intelligence
- Build sourcing pipelines across multiple job titles and cities at once
- Identify which companies are hiring for specific roles
- Track applicant counts to gauge competition for specific roles

---

## Example tasks

Ready-to-run configurations for common jobs. Run one as-is, then swap in
your own keywords, locations, or companies.

### 🧑‍💻 Scrape Remote Software Engineer Jobs Posted Today (US)

Remote software engineer roles posted on LinkedIn in the last 24 hours,
built for a daily feed. No login or API key.

```json
{
  "keywords": "software engineer",
  "location": "United States",
  "workType": "2",
  "datePosted": "past_24_hours",
  "maxResults": 100
}
```

### 📈 Find New Sales Roles Companies Are Hiring for This Week

New Account Executive, SDR, and BDR openings from the past week. A company
staffing up sales has budget: turn it into a prospect list.

```json
{
  "keywordsList": ["account executive", "sales development representative", "business development representative"],
  "location": "United States",
  "datePosted": "past_week",
  "fetchJobDetails": true,
  "maxResultsPerSearch": 50
}
```

### 🎯 Track Director Openings at Companies You're Watching

Director openings at a named list of companies. Put each company name in the
search so LinkedIn surfaces its jobs, then filter to Director level. Use
distinctive company names, since `companyFilter` matches by substring.

```json
{
  "keywordsList": ["Stripe", "Plaid", "Brex", "Marqeta", "Adyen"],
  "location": "United States",
  "companyFilter": ["stripe", "plaid", "brex", "marqeta", "adyen"],
  "experienceLevel": "5",
  "fetchJobDetails": true,
  "maxResultsPerSearch": 100
}
```

### 📊 Scrape Data and AI Jobs Across Top US Tech Cities

Three data and AI roles across four US tech hubs in one batch run,
deduplicated and tagged by the search that found each job.

```json
{
  "keywordsList": ["data engineer", "data scientist", "machine learning engineer"],
  "locationsList": ["New York, NY", "San Francisco, CA", "Austin, TX", "Seattle, WA"],
  "datePosted": "past_month",
  "maxResultsPerSearch": 50
}
```

### 🕵️ Monitor One Company's New Job Postings Every Week

One company's new postings from the past week. Put the company name in the
search, filter to it, and diff run over run to read where it is scaling.

```json
{
  "keywords": "Stripe",
  "location": "United States",
  "datePosted": "past_week",
  "companyFilter": ["stripe"],
  "maxResults": 100
}
```

### 🏥 Build a Weekly Nursing Job Feed for Any US Metro

Registered nurse and nurse practitioner roles posted this week across major
US metros, tagged by city so rows route to the right recruiter.

```json
{
  "keywordsList": ["registered nurse", "nurse practitioner"],
  "locationsList": ["New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX"],
  "datePosted": "past_week",
  "maxResultsPerSearch": 50
}
```

---

## Key features

- **No API key, login, or cookies** — scrapes public pages only
- **No browser / no Playwright** — pure HTTP, lower cost, faster execution
- **Parallel pagination** — search pages fetched concurrently for up to ~4x faster runs
- **Batch search** — multiple keywords × locations in one run
- **Full job details** — description, seniority, employment type, job function, industry, applicant count
- **Company info** — employee count, industry, logo when shown on the job page
- **Title-only filter** — keep only jobs whose title matches your keyword
- **Description HTML** — raw HTML alongside plain text
- **Deduplication** — jobId-based dedup across all batch searches
- **Company filter** — whitelist specific companies by name or slug
- **Smart early-stop** — abandons a search the moment its result pool is exhausted, saving compute and proxy cost
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
  "workplaceType": "Remote (per LinkedIn)",

  "description": "We are looking for a Senior Data Engineer...",
  "descriptionHtml": "<div class=\"show-more-less-html__markup\">...</div>",
  "seniorityLevel": "Mid-Senior level",
  "employmentType": "Full-time",
  "jobFunction": "Engineering and Information Technology",
  "industries": "Financial Services",
  "applicantCount": "Over 200 applicants",

  "companyEmployeeCount": "1,001-5,000 employees",
  "companyIndustry": "Financial Services"
}
```

Fields `description`, `descriptionHtml`, `seniorityLevel`, `employmentType`, `jobFunction`, `industries`, `applicantCount`, and `companyIndustry` require `fetchJobDetails: true`. `companyEmployeeCount` requires `fetchCompanyDetails: true`. `companyEmployeeCount` and `companyIndustry` appear only when LinkedIn shows them on the job or company page. `salary` is returned without `fetchJobDetails`, but is filled in far more often with it — see [On `salary`](#on-salary).

### On `salary`

`salary` comes from the search card when LinkedIn prints a range there, which
is uncommon — most cards carry no pay data at all. Enabling
`fetchJobDetails: true` fills the gap: the job page is checked for a
JSON-LD `baseSalary` block and then for a visible pay-range element, and
either one is used when the card came back empty. A card value is never
overwritten.

In a 3-row sample, listing-only returned no salary on any row while detail
mode recovered a range on 2 of 3. If pay data matters to your use case, run
with `fetchJobDetails: true` — it costs one extra request per job. Coverage
still depends on the employer publishing a range at all, so expect gaps.

### On `workplaceType`

`workplaceType` records which work-arrangement bucket LinkedIn returned the job from, so it is only set when you pass a `workType` filter. LinkedIn's on-site / remote / hybrid buckets are mutually exclusive, so a row labelled `Remote (per LinkedIn)` is one LinkedIn itself classifies as remote.

That label reflects **how the employer tagged the posting**, not what the description says. Employers frequently tag a hybrid role as Remote and LinkedIn does not validate it, so a remote-filtered result can still mention office days in its text. There is no separate remote/hybrid flag anywhere in LinkedIn's public job data to cross-check against — if you need description-level certainty, enable `fetchJobDetails` and post-filter on `description` yourself.

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
| `titleOnly` | boolean | `false` | Keep only jobs whose **title** contains the keyword (see note below) |
| `datePosted` | select | any | `past_24_hours`, `past_week`, `past_month` |
| `jobType` | select | any | Full-time, Part-time, Contract, etc. |
| `experienceLevel` | select | any | Entry, Associate, Mid-Senior, Director, etc. |
| `workType` | select | any | On-site, Remote, Hybrid |
| `salary` | select | any | Minimum salary filter (USD) |
| `fetchJobDetails` | boolean | `false` | Load full detail page per job (description, criteria, applicants) |
| `fetchCompanyDetails` | boolean | `false` | Also fetch each company's public page for employee count (one request per unique company, cached) |
| `maxResults` | integer | 100 | Total result cap across all searches |
| `maxResultsPerSearch` | integer | 100 | Cap per keyword/location combo (batch mode) |
| `proxyConfiguration` | object | RESIDENTIAL | Proxy settings — residential recommended |

> **Using `titleOnly`?** Use **plain keywords** (e.g. `product analyst`, `growth analyst`), not Boolean strings. The title filter matches your text against the job title directly — it does **not** interpret LinkedIn Boolean operators like `AND`/`OR` or quotation marks. A keyword like `"product" AND "analyst"` with `titleOnly: true` will match nothing, because no job title literally contains that operator text. If you want Boolean search, set `titleOnly: false` and let LinkedIn's search engine handle the operators.

> **Note on result counts with `titleOnly`:** because LinkedIn has no native title-scope filter, results are filtered on our side — a niche role can return far fewer than `maxResults`. That's expected: the run stops automatically once every matching title is found, rather than padding with description-only matches.

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
  "maxResultsPerSearch": 100
}
```

Output includes job descriptions, seniority, employment type, industry, and applicant counts — ready to pipe into your CRM.

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

Once connected, your AI agent can search LinkedIn jobs, pull full job details, and track hiring trends — all from a natural language prompt.

---

## Proxy guidance

LinkedIn aggressively blocks datacenter IPs. **Residential proxies are required.** The actor defaults to Apify's RESIDENTIAL proxy group and will fail immediately on Apify if no proxy is configured — this saves you compute on a run that would never succeed anyway.

Without residential proxies, LinkedIn blocks the first request on almost every run. With residential proxies, the actor reliably handles large batch runs.

---

## Timeout & memory guidance

The actor applies a short, jittered politeness delay and fetches up to 5 requests concurrently to stay under LinkedIn's radar without wasting time. Search pages are paginated in concurrent batches, and with `fetchJobDetails: true` each job's detail request fans out concurrently per page — so runtime scales gently with result count.

| Max results | fetchJobDetails | Est. runtime | Recommended timeout |
|---|---|---|---|
| 25 (free tier) | false (enforced) | ~30 sec | 120s |
| 50 | true | ~1 min | 300s |
| 100 | true | ~2-3 min | 600s |
| 200 | true | ~4-5 min | 900s |
| 100 | false (search only) | ~15 sec | 120s |

> **Free tier note:** Free users (25 results max) always run with `fetchJobDetails: false` — listing data only (title, company, location, salary, URL, posted date). Subscribe for full job details: description, seniority, employment type, job function, industry, and applicant count.

> **Proxy data cap:** To protect against runaway proxy cost on blocked or pathological runs, the actor aborts early if a single run downloads far more data than its result count warrants (floor 25 MB + ~0.5 MB per requested result). It keeps and returns everything scraped up to that point. Lower `maxResults` or disable enrichment for very large runs.

**Memory:** 512MB is sufficient for all run sizes. 1-2GB is not needed unless you are running very large batch jobs (500+ results).

To set timeout in Apify: go to your actor run settings → **Timeout** → set in seconds.

---

## Limitations

- LinkedIn caps search pagination at 1,000 results per query — use multiple searches or tighter filters to go deeper
- Salary data is only present when LinkedIn displays it on the listing or job page
- Company employee count, industry, and logo appear only when LinkedIn shows them on the job page
- `fetchJobDetails` adds one request per job — higher cost and runtime; enable only when you need the detail fields
- Skills and recruiter/hiring-manager data are login-gated by LinkedIn and not available from public pages, so they are not included
