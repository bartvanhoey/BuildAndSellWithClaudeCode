# Onboarding Workflow — One-Time Setup

## Purpose
Populate `company_profile.json` so the competitor analysis workflow has a complete company context. Run this once before the first weekly report. Re-run any time the company's positioning or competitive landscape changes significantly.

## Prerequisites
- `.env` file exists with `ANTHROPIC_API_KEY` set
- `brand_assets/` folder contains `Logo.png` and `colors.txt`

## Steps

### Step 1 — Check for existing profile
Read `company_profile.json`. If `company_name` is non-empty, ask the user:
> "A company profile already exists for **{company_name}**. Do you want to update it or keep it as-is?"

If keeping as-is, stop here.

### Step 2 — Collect company information
Ask the user the following questions one at a time (do not dump them all at once):

1. **Company name** — What is your company called?
2. **Website** — What is your primary website URL? (e.g., `https://example.com`)
3. **Industry** — What industry or niche are you in? Be specific (e.g., "B2B SaaS project management tools" not just "software").
4. **Description** — In 1-2 sentences, what does your company do?
5. **Target audience** — Who is your ideal customer? (role, company size, pain points)
6. **Value proposition** — What's the core reason customers choose you over alternatives?
7. **Known competitors** — List any competitors you already know about (comma-separated). It's fine if this is empty — the workflow will discover them.
8. **Search keywords** — What 3-5 search terms do your customers use to find solutions like yours?
9. **Google Drive folder ID** — Paste the folder ID from Google Drive where reports should be uploaded. (Optional — leave blank to skip Drive upload and keep reports in `.tmp/`.)

### Step 3 — Write profile
Once all answers are collected, write `company_profile.json` with the user's responses. Format `known_competitors` and `search_keywords` as JSON arrays.

Example final structure:
```json
{
  "company_name": "Acme Corp",
  "website": "https://acme.com",
  "industry": "B2B SaaS project management",
  "description": "Acme helps remote engineering teams ship faster with async-first project tracking.",
  "target_audience": "Engineering managers at 50-500 person tech companies frustrated with Jira complexity",
  "value_proposition": "Jira-level power without the setup overhead — up and running in one afternoon",
  "known_competitors": ["Linear", "Shortcut", "Asana"],
  "search_keywords": ["project management software", "jira alternative", "engineering team tools", "agile tracking software"],
  "google_drive_folder_id": "1AbCdEfGhIjKlMnOpQrStUv"
}
```

### Step 4 — Verify brand assets
Call `tools/parse_brand_assets.py`. Confirm it outputs `.tmp/brand_config.json` with:
- `primary_color`: `#093824`
- `secondary_color`: `#c0652a`
- `logo_path`: absolute path to `brand_assets/Logo.png`

If `Logo.png` is missing, warn the user — the PDF cover page will fall back to a text-only header.

### Step 5 — Confirm setup
Tell the user:
> "Setup complete. `company_profile.json` is ready. Run the competitor analysis workflow whenever you're ready for your first report."

## Edge Cases
- **User skips Google Drive folder ID**: Set `google_drive_folder_id` to `""`. The upload step will skip gracefully and leave the PDF in `.tmp/`.
- **User unsure about search keywords**: Suggest 3-4 based on their industry and description, and let them confirm.
- **User wants to add competitors mid-cycle**: Direct them to `workflows/manual_competitor_add.md`.
