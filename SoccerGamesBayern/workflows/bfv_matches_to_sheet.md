# Workflow: BFV Upcoming Matches → Google Sheet → Email

## Objective
Scrape upcoming Kreisliga and Bezirksliga matches from bfv.de for the next 14 days,
write them into a formatted Google Sheet, and email the sheet link to the recipient.

## Required Inputs
- Internet access (to scrape bfv.de)
- `credentials.json` in project root (Google OAuth — Gmail + Sheets + Drive)
- `GMAIL_SENDER` set in `.env`
- `email_recipient` set in `config.json` (default: bartvanhoey@hotmail.com)
- `fonttools` Python package installed (`pip install fonttools`)

## Outputs
- `.tmp/matches_YYYY-MM-DD.json` — raw scraped match data
- A new Google Sheet with formatted match table (975+ rows for all leagues)
- An HTML email delivered to the recipient with the sheet link

## Steps

### Step 1 — Scrape BFV matches
```bash
python tools/scrape_bfv_matches.py
```

**How it works (important — do not simplify):**
- Calls `https://next.bfv.de/bfv-api/v1/public/getBfvWamThree/...` to get all competition IDs
- For each competition, fetches spieltag pages using `/spieltag/N` URL path
- BFV uses **per-request custom fonts** to obfuscate text (anti-scraping measure)
  - Each page response embeds a unique font ID (e.g. `kg6ky627`)
  - The font maps private-use unicode chars (U+E000–U+F8FF) to standard glyph names
  - `fonttools` decodes the font → builds a unicode→char map → decodes the HTML
- Extracts match rows by splitting on weekday patterns (Mo/Di/Mi/Do/Fr/Sa/So)
- Future matches show `- : -` as the separator between home and away team
- Filters to matches within the next `lookahead_days` days
- Saves to `.tmp/matches_YYYY-MM-DD.json`

**Check output:** Confirm JSON contains match objects with date, time, home_team, visitor_team

### Step 2 — Create Google Sheet
```bash
python tools/create_google_sheet.py --input .tmp/matches_YYYY-MM-DD.json
```
- Authenticates via OAuth (browser pop-up on first run)
- Creates a new Google Sheet titled "BFV Upcoming Matches — YYYY-MM-DD"
- Writes header row + all match rows
- Applies formatting: blue header, bold text, frozen row, auto-resized columns
- Outputs JSON with `sheet_url` and `row_count`

### Step 3 — Send Email
```bash
python tools/send_email.py --sheet-url "<URL from Step 2>" --row-count <N>
```
- Sends an HTML email to `email_recipient` in config.json
- Email contains a styled button linking to the Google Sheet
- Saves receipt to `.tmp/receipts/email_receipt_YYYY-MM-DD.json`

## Edge Cases & Known Issues

### Google OAuth — first run (Sheets + Drive scopes needed)
The Google Cloud project needs **Google Sheets API** and **Google Drive API** enabled:
1. Go to console.cloud.google.com → project `youtubeanalysis-491113`
2. APIs & Services → Library → enable Google Sheets API + Google Drive API
3. Delete `token.json` if it exists (it may have only gmail.send scope)
4. Re-run Step 2 — browser consent screen will request all 3 scopes

### Font obfuscation changes
If decoded text looks like garbage (random letters/symbols):
- The font format hasn't changed — BFV still uses private-use unicode + TTF font
- But the glyph names in the font may be different
- Check: `fonttools` cmap shows glyph names like `'zero'`, `'one'`, `'A'`, etc.
- Update `GLYPH_TO_CHAR` in `scrape_bfv_matches.py` if new glyph names appear

### Competition list changes
- The WAM3 API (`next.bfv.de/bfv-api/v1/public/getBfvWamThree/...`) returns all leagues
- Kreisliga spielklasse_id = `392`, Bezirksliga = `390`
- Season code is `2526` for 2025/26 — update for new seasons

### Spieltag detection
- Script loads the default competition page to find current spieltag number
- Then checks current + next 3 spieltage for matches in the date window
- If a league uses unusual spieltag counts (e.g. Pokal), some may be missed
- Workaround: increase the range in `scrape_league()` from `+4` to `+6`

### fonttools not found
```
pip install fonttools
```

### Rate limiting / connection errors
- Script uses 0.5s delay between spieltag requests, 1s between competitions
- If errors occur, increase `time.sleep()` values in `scrape_bfv_matches.py`

## Configuration
Edit `config.json` to adjust:
- `leagues` — list of league names to scrape (`Kreisliga`, `Bezirksliga`, `Kreisklasse`, etc.)
- `lookahead_days` — how many days ahead to look (default: 14)
- `email_recipient` — who gets the email
- `email_subject_template` — subject line (use `{date}` placeholder)

## Typical run results (2026-03-25)
- Kreisliga: 43 competitions, 707 upcoming matches
- Bezirksliga: ~20 competitions, 268 upcoming matches
- Total: ~975 matches across Bavaria
- Runtime: ~3-4 minutes (network-bound)
