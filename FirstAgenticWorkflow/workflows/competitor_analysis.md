# Competitor Analysis Workflow — Weekly SOP

## Purpose
Produce a branded PDF competitor intelligence report every Monday morning. The report covers pricing, messaging, SEO signals, recent news, and social presence for up to 8 competitors. The PDF is uploaded to Google Drive and a shareable link is returned.

## Trigger
- **Scheduled**: Weekly via Windows Task Scheduler (Monday 07:00 AM) using `run_workflow.py`
- **Manual**: Run this workflow directly in a conversation when you want an on-demand report

## Prerequisites
- `company_profile.json` is populated (run `workflows/onboarding.md` if not)
- `.env` contains `ANTHROPIC_API_KEY` and `SERPER_API_KEY`
- `credentials.json` exists for Google Drive upload (optional — upload step skips gracefully if absent)

---

## Phase 0 — Setup

### Step 0.1 — Load company profile
Read `company_profile.json`. Check that `company_name` is non-empty.

**If missing or empty**: Stop. Tell the user to run `workflows/onboarding.md` first and do not proceed.

### Step 0.2 — Parse brand assets
Run:
```
python tools/parse_brand_assets.py
```
Confirm `.tmp/brand_config.json` is written with `primary_color`, `secondary_color`, and `logo_path`.

---

## Phase 1 — Competitor Discovery

### Step 1.1 — Search for competitors
Run `tools/search_web.py` with these queries (substitute values from `company_profile.json`):
- `"{industry} competitors"`
- `"alternatives to {company_name}"`
- `"{industry} top tools {current_year}"`
- `"{search_keywords[0]} best software"` (use first keyword)

```
python tools/search_web.py --query "<query>" --num 10
```

### Step 1.2 — Deduplicate and cap at 8
From the search results, extract domain names and company names. Merge with `known_competitors` from the profile. Deduplicate. Keep the top 8 most relevant by industry fit. If more than 8 are found, prioritize established players and direct competitors.

### Step 1.3 — Update company_profile.json
Write the final competitor list back to `company_profile.json` under `known_competitors`. This persists discoveries for future runs.

---

## Phase 2 — Pricing & Offers

For each competitor (run sequentially — Serper has rate limits):

### Step 2.1 — Scrape pricing page
Try these URLs in order, stop at first success:
1. `{competitor_domain}/pricing`
2. `{competitor_domain}/plans`
3. `{competitor_domain}` (homepage fallback)

```
python tools/scrape_page.py --url "https://{domain}/pricing" --mode pricing
```

If the result contains `"error"`, note it in `scrape_errors` for that competitor and continue.

### Step 2.2 — Search for pricing
```
python tools/search_web.py --query '"{competitor_name}" pricing {current_year}' --num 5
```

---

## Phase 3 — Messaging & Positioning

For each competitor:

### Step 3.1 — Scrape homepage
```
python tools/scrape_page.py --url "https://{domain}" --mode messaging
```

Captures: H1, meta description, CTAs, top paragraphs.

---

## Phase 4 — Content & SEO

For each competitor:

### Step 4.1 — Site search + keyword ranking
```
python tools/search_web.py --query "site:{domain}" --num 5
```

For each of the user's `search_keywords`, run:
```
python tools/search_web.py --query '"{search_keyword}" {domain}' --num 3
```

This reveals which user-relevant keywords the competitor ranks for.

---

## Phase 5 — Social & News

### Step 5.1 — Recent news (past 7 days)
For each competitor:
```
python tools/serper_news.py --query "{competitor_name}" --num 10
```

If the result is empty or contains only an error, record `"No activity past 7 days"`.

### Step 5.2 — Social profiles
For each competitor:
```
python tools/extract_social_signals.py --company "{competitor_name}" --domain "{domain}"
```

---

## Phase 6 — Assembly

### Step 6.1 — Write executive summary
Write 2-3 paragraphs covering:
1. **Market landscape**: How many competitors found, overall pricing range, common positioning themes
2. **Key findings**: The most significant changes or differentiators this week (new pricing, product launches, news, etc.)
3. **Recommended actions**: 2-3 concrete actions the user could take based on the findings

### Step 6.2 — Construct report_data JSON
Build a JSON object following this schema:
```json
{
  "company": { ...full contents of company_profile.json... },
  "generated_date": "YYYY-MM-DD",
  "executive_summary": "<your 2-3 paragraph prose>",
  "competitors": [
    {
      "name": "CompetitorName",
      "domain": "example.com",
      "pricing": {
        "pricing_text": ["$29/mo Starter", "$99/mo Pro", ...],
        "search_results": [...top 3 search result snippets...],
        "notes": "Optional summary note"
      },
      "messaging": {
        "h1": [...],
        "meta_description": "...",
        "ctas": [...],
        "notes": ""
      },
      "seo": {
        "search_results": [...],
        "keyword_hits": { "keyword1": true/false, ... },
        "notes": ""
      },
      "news": [
        { "title": "...", "link": "...", "date": "...", "source": "..." }
      ],
      "social": {
        "linkedin_url": "...",
        "twitter_url": "..."
      },
      "scrape_errors": []
    }
  ]
}
```

### Step 6.3 — Save report data
Pipe or write the JSON to:
```
python tools/assemble_report_data.py
```
This writes `.tmp/report_data_YYYY-MM-DD.json`.

### Step 6.4 — Generate PDF
```
python tools/generate_pdf.py
```
This writes `.tmp/competitor_report_YYYY-MM-DD.pdf`.

---

## Phase 7 — Delivery

### Step 7.1 — Upload to Google Drive
```
python tools/upload_to_drive.py --file ".tmp/competitor_report_YYYY-MM-DD.pdf" --folder-id "{google_drive_folder_id}"
```

**If `credentials.json` is missing**:
Report: "Google Drive upload skipped — credentials.json not found. PDF available at `.tmp/competitor_report_YYYY-MM-DD.pdf`. See Google Cloud Console setup instructions."
Do not fail the run.

**If `google_drive_folder_id` is empty**:
Run the upload without `--folder-id`. The file will go to the root of Drive.

### Step 7.2 — Final report to user
Provide:
- Shareable Drive link (or local path if upload was skipped)
- Count of competitors analyzed
- Any competitors with scrape errors (flag for manual review)
- Date of next scheduled run

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Scraper returns `{"error": "blocked_403"}` | Record in `scrape_errors`, note in report, continue |
| No news results for a competitor | Record `"No activity past 7 days"` — this itself is intelligence |
| `company_profile.json` missing | Halt, instruct user to run `onboarding.md` |
| `credentials.json` missing | Skip upload, keep PDF in `.tmp/`, report local path |
| >8 competitors discovered | Keep top 8 by direct relevance; log excluded names |
| Phase fails mid-run | `.tmp/` files from completed phases persist. On retry, check which `report_data_*.json` files exist — skip re-running completed competitors |
| Serper rate limit (429) | Wait 10 seconds, retry once. If still failing, note affected competitor and continue |
| `SERPER_API_KEY` missing | Halt with clear error message pointing to `.env` |

## Notes & Lessons Learned
- Serper `tbs=qdr:w` filters news to the past week — confirmed working as of 2026-03
- Some SaaS pricing pages use JavaScript rendering; scraper captures server-rendered fallback only
- LinkedIn blocks direct scraping; `extract_social_signals.py` uses search-based discovery instead
