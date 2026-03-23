# Workflow: Scrape Job Listings from DailyRemote

## Objective
Scrape all job listings from DailyRemote matching a given search term and location, then export the results to an Excel file.

## Inputs
| Input | Default | Description |
|-------|---------|-------------|
| `--search` | `"social media"` | Search keyword(s) |
| `--location` | `"United States"` | Location filter (country name as shown on DailyRemote) |
| `--output` | `job_listings.xlsx` | Output filename (saved relative to CWD) |
| `--max-pages` | `50` | Safety cap on pages to scrape |

## Tool
`tools/scrape_dailyremote.py`

## How to Run
From the `AgenticWorkflowDemo/` directory:

```bash
# Default: social media jobs in United States
python tools/scrape_dailyremote.py

# Custom search
python tools/scrape_dailyremote.py --search "content marketing" --location "United States" --output content_jobs.xlsx
```

## Expected Output
- Excel file with columns: **Title | Company | Location | Date Posted | Job URL**
- One row per unique job listing
- Approximately 20 listings per page; ~14 pages for "social media" → ~266 rows

## Known Constraints

### Company Names (Paywall)
DailyRemote hides company names behind a premium subscription. The `Company` column will show `N/A (Premium)` for most listings unless the name is exposed in the HTML. This is expected behavior.

### Pagination
The script stops automatically when a page returns 0 job cards. No manual page count needed.

### Rate Limiting
- A 1.5-second delay is built in between page requests.
- If you get blocked (HTTP 429 or empty results mid-scrape), increase `REQUEST_DELAY` in the script.

### HTML Structure Changes
DailyRemote may update its HTML structure. If the scraper returns 0 results or missing fields:
1. Visit the URL manually in a browser
2. Inspect a job card element (right-click → Inspect)
3. Update the CSS selectors in `parse_job_cards()` and `extract_job_data()` in `tools/scrape_dailyremote.py`
4. Update this workflow with the new selectors

## Verification Checklist
- [ ] `job_listings.xlsx` created in the working directory
- [ ] Row count matches approximate total shown on DailyRemote (~266 for "social media")
- [ ] Job URLs follow format: `https://dailyremote.com/remote-job/[slug]`
- [ ] Title and Date Posted columns populated
- [ ] Company column shows names or `N/A (Premium)`

## Edge Cases
- **Empty results on page 1**: Check if DailyRemote changed its HTML structure or is blocking the scraper. Try visiting the URL in a browser to confirm listings exist.
- **Duplicate URLs**: The script deduplicates by job URL automatically.
- **Partial scrape**: If the script errors mid-run, the Excel file won't be saved. Re-run from scratch.
