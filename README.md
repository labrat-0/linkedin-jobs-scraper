# LinkedIn Jobs Scraper

Scrape LinkedIn job listings at scale. No API keys, no browser, no login required. Fast, lightweight HTTP-based scraping with structured output. MCP-ready for AI agent integration.

## What it does

This actor scrapes job listings from LinkedIn's public job search pages. It extracts job titles, companies, locations, salaries, posting dates, and optionally fetches full job details including descriptions, seniority level, employment type, job function, and industries. Returns clean JSON with consistent fields -- ready for analysis, job market research, or consumption by AI agents via MCP.

## Key features

- **No authentication needed** -- scrapes public pages only, no LinkedIn account required
- **HTTP-only** -- no browser or headless Chrome, which means lower cost and faster execution
- **Rich filters** -- search by keywords, location, date posted, job type, experience level, work arrangement, and salary range
- **Full job details** -- optionally loads each job's detail page for complete descriptions, seniority level, employment type, job function, industries, and applicant count
- **Structured output** -- clean JSON with consistent fields, ready for analysis or integration
- **Salary extraction** -- captures salary data when LinkedIn displays it
- **AI agent tooling** -- expose as an MCP tool so AI agents can search LinkedIn jobs, track hiring trends, and pull job market data in real time

## Input parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `keywords` | string | Job search keywords (e.g. "python developer", "data engineer") |
| `location` | string | Location filter (e.g. "United States", "San Francisco, CA") |
| `geoId` | string | LinkedIn geographic ID for precise location (e.g. "103644278" for US) |
| `datePosted` | string | Filter by date: "past_24_hours", "past_week", "past_month" |
| `jobType` | string | Job type: F (Full-time), P (Part-time), C (Contract), T (Temporary), V (Volunteer), I (Internship), O (Other) |
| `experienceLevel` | string | Experience: 1 (Internship), 2 (Entry), 3 (Associate), 4 (Mid-Senior), 5 (Director), 6 (Executive) |
| `workType` | string | Work arrangement: 1 (On-site), 2 (Remote), 3 (Hybrid) |
| `salary` | string | Minimum salary range: 1 ($40K+) through 9 ($200K+) |
| `fetchJobDetails` | boolean | Load full detail pages for descriptions, seniority, etc. (default: true) |
| `maxResults` | integer | Maximum results to return, up to 1,000 (default: 100) |
| `proxyConfiguration` | object | Proxy settings. Residential proxies recommended. |

## Output format

Each job listing is output as a JSON object:

```json
{
  "jobId": "3812345678",
  "title": "Senior Python Developer",
  "company": "Acme Corp",
  "companyUrl": "https://www.linkedin.com/company/acme-corp",
  "location": "San Francisco, CA",
  "postedDate": "2 days ago",
  "postedDateTimestamp": "2025-02-12",
  "salary": "$150,000 - $200,000",
  "url": "https://www.linkedin.com/jobs/view/3812345678",
  "description": "We are looking for a Senior Python Developer...",
  "seniorityLevel": "Mid-Senior level",
  "employmentType": "Full-time",
  "jobFunction": "Engineering and Information Technology",
  "industries": "Technology, Information and Internet",
  "applicantCount": "Over 200 applicants"
}
```

When `fetchJobDetails` is disabled, the `description`, `seniorityLevel`, `employmentType`, `jobFunction`, `industries`, and `applicantCount` fields will be empty strings.

## Proxy configuration

LinkedIn may block requests from datacenter IPs. **Residential proxies are recommended** for reliable scraping. The actor is configured to use Apify's residential proxy group by default.

## Limitations

- LinkedIn caps search results at **1,000 per query**. Use more specific filters to access different result sets.
- Free users are limited to **25 results per run**. Subscribe to the actor for unlimited results up to 1,000.
- Rate limiting is built in (5 seconds between requests) to avoid blocks.
- Job detail fetching makes one additional request per job, which increases proxy usage and run time.

## Cost estimation

With pay-per-event pricing at **$0.50 per 1,000 results**:

| Results | Actor cost | Estimated proxy cost | Total |
|---------|-----------|---------------------|-------|
| 100 jobs (with details) | $0.05 | ~$0.10 | ~$0.15 |
| 500 jobs (with details) | $0.25 | ~$0.50 | ~$0.75 |
| 1,000 jobs (with details) | $0.50 | ~$1.00 | ~$1.50 |
| 100 jobs (no details) | $0.05 | ~$0.02 | ~$0.07 |

## Use cases

- **Job market research** -- track which skills are in demand, salary trends, hiring patterns
- **Competitive intelligence** -- monitor competitors' hiring activity
- **Lead generation** -- find companies actively hiring in your space
- **Career planning** -- aggregate and compare job listings across locations and industries
- **Academic research** -- analyze labor market data at scale
- **AI agent tooling** -- expose as an MCP tool so AI agents can search job listings, compare salaries, and monitor hiring trends in real time

---

## MCP Integration

This actor works as an MCP tool through Apify's hosted MCP server. No custom server needed.

- **Endpoint:** `https://mcp.apify.com?tools=labrat011/linkedin-jobs-scraper`
- **Auth:** `Authorization: Bearer <APIFY_TOKEN>`
- **Transport:** Streamable HTTP
- **Works with:** Claude Desktop, Cursor, VS Code, Windsurf, Warp, Gemini CLI

**Example MCP config (Claude Desktop / Cursor):**

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

AI agents can use this actor to search LinkedIn job listings, track salary trends, monitor hiring activity, and pull structured job market data -- all as a callable MCP tool.

---

## Feedback

Found a bug or have a feature request? Open an issue on the actor's Issues tab in Apify Console.
