# Manual Competitor Add — Utility Workflow

## Purpose
Add a new competitor to `company_profile.json` mid-cycle without waiting for the next weekly run. Optionally run a targeted analysis on just the new competitor.

## When to Use
- You just learned about a new competitor and want to include them in future reports
- A competitor's domain changed or you want to correct an entry
- You want to remove a competitor that's no longer relevant

---

## Add a Competitor

### Step 1 — Get competitor details
Ask the user:
1. **Company name** (e.g., "Notion")
2. **Domain** (e.g., "notion.so")

### Step 2 — Check for duplicates
Read `company_profile.json`. Check if the company name or domain already appears in `known_competitors`. If so, tell the user it's already tracked and ask if they want to update the entry.

### Step 3 — Update company_profile.json
Add the new competitor to `known_competitors` as a string (just the company name). Write the updated file.

### Step 4 — Optional: Run spot analysis
Ask: "Would you like me to run a quick analysis on {competitor_name} right now? This will fetch their pricing, homepage messaging, recent news, and social profiles."

If yes, run these tools in order:
```
python tools/scrape_page.py --url "https://{domain}/pricing" --mode pricing
python tools/scrape_page.py --url "https://{domain}" --mode messaging
python tools/serper_news.py --query "{competitor_name}" --num 10
python tools/extract_social_signals.py --company "{competitor_name}" --domain "{domain}"
```

Summarize findings in plain text (no PDF needed for spot analyses).

---

## Remove a Competitor

### Step 1 — Confirm removal
Read `company_profile.json` and show the current `known_competitors` list. Ask the user to confirm which one to remove.

### Step 2 — Update company_profile.json
Remove the competitor from the list and write the updated file.

Confirm: "Removed {name} from the competitor list. They will not appear in next week's report."

---

## Edge Cases
- **Competitor at cap (8)**: If there are already 8 in the list, warn the user: "You have 8 competitors tracked — the maximum for a single report. Adding another will drop the last one alphabetically unless you remove one manually." Then ask how to proceed.
- **Domain not provided**: Try inferring from the company name by searching `"{company_name}" official website` via `tools/search_web.py`. Confirm with the user before saving.
