# YouTube Trend Analysis Workflow — Weekly SOP

## Purpose
Produce a weekly YouTube trend report for the AI/automation niche and deliver it as a professional `.pdf` brand report via Gmail. The report helps the creator understand what's trending, who's winning, and what content ideas are underserved.

## Trigger
- **Scheduled**: Weekly (e.g., Monday 07:00 AM) via Windows Task Scheduler
- **Manual**: Run this workflow directly in a conversation for an on-demand report

---

## Prerequisites

| Requirement | Where |
|---|---|
| `YOUTUBE_API_KEY` | `.env` — YouTube Data API v3 key from Google Cloud Console |
| `GMAIL_SENDER` | `.env` — Gmail address used as sender |
| `email_recipient` | `config.json` — where the report is delivered |
| `credentials.json` | Project root — Google OAuth client secret (Gmail API enabled) |
| Python dependencies | Run `pip install -r requirements.txt` once |

---

## Phase 0 — Pre-flight

### Step 0.1 — Check API key
Confirm `YOUTUBE_API_KEY` is set in `.env` and non-empty. If missing, stop and instruct the user to create a key at Google Cloud Console → APIs & Services → Credentials and enable YouTube Data API v3.

### Step 0.2 — Check config
Confirm `config.json` exists and `search_terms` is non-empty. If missing, stop.

### Step 0.3 — Check Gmail credentials
Confirm `credentials.json` exists. If missing, warn and note the email delivery step will fail — but continue with data collection and report generation. The local `.pdf` file will still be available in `.tmp/decks/`.

### Step 0.4 — Set date prefix
Today's date in `YYYY-MM-DD` format is the date prefix used by all tools. All intermediate files will be date-stamped.

---

## Phase 1 — Data Collection

Run tools **in sequence** (each depends on the previous output).

### Step 1.1 — Fetch Trending Videos
```
python tools/fetch_trending_videos.py
```
**Output**: `.tmp/raw_videos_YYYY-MM-DD.json`
**Expected**: 30–100 video stubs.
**If < 10 results**: Warn. Consider widening `published_within_days` in `config.json` (try 30).

### Step 1.2 — Fetch Video Statistics
```
python tools/fetch_video_stats.py
```
**Output**: `.tmp/video_stats_YYYY-MM-DD.json`
**Expected**: Same count as raw_videos (minus any deleted/private videos).
**Confirms**: Each video has `view_count`, `like_count`, `duration_seconds`.

### Step 1.3 — Fetch Channel Statistics
```
python tools/fetch_channel_stats.py
```
**Output**: `.tmp/channel_stats_YYYY-MM-DD.json`
**Expected**: 10–50 unique channels.

### Step 1.4 — Fetch Transcripts
```
python tools/fetch_transcripts.py
```
**Output**: `.tmp/transcripts_YYYY-MM-DD.json`
**Expected**: Transcripts for up to 20 videos (top by view count). Some will have errors (`TranscriptsDisabled`, `NoTranscriptFound`) — this is normal and does not halt the workflow.
**Note**: No YouTube API quota consumed. Uses `youtube-transcript-api`.

---

## Phase 2 — Analysis

### Step 2.1 — Run Analysis
```
python tools/analyze_trends.py
```
**Output**: `.tmp/analysis_YYYY-MM-DD.json`

This produces all derived metrics:
- View velocity rankings
- Engagement rate rankings
- Top channels by dataset views
- Title keyword frequency (stop words excluded)
- Transcript n-gram themes
- Content gap detection

### Step 2.2 — Write Executive Summary (Agent Task)
Read `.tmp/analysis_YYYY-MM-DD.json`. Write a 4–6 sentence executive summary covering:
1. Total videos and channels analyzed, data period
2. The single fastest-growing video and what makes it notable
3. Dominant keyword theme(s) this week
4. One concrete, actionable recommendation

Insert as `"executive_summary"` in the analysis JSON and save.

### Step 2.3 — Write Channel Spotlights (Agent Task)
For the top 3 channels in `top_channels`, write a 1-sentence description of their apparent content strategy based on their video titles in the dataset.

Insert as `"channel_spotlights"` in the analysis JSON (a list of 3 strings) and save.

### Step 2.4 — Write Content Recommendations (Agent Task)
From `content_gaps` and `keyword_frequency`, draft 5–7 specific YouTube video title recommendations the creator could act on this week.

Insert as `"recommendations"` in the analysis JSON (a list of strings) and save.

### Step 2.5 — Save Updated Analysis
Write the enriched analysis back to `.tmp/analysis_YYYY-MM-DD.json` before proceeding to Phase 3.

---

## Phase 3 — Report Generation

### Step 3.1 — Build PDF Report
```
python tools/build_pdf_report.py
```
**Output**: `.tmp/decks/youtube_trends_YYYY-MM-DD.pdf`

Verify the file exists and is non-zero bytes before continuing. If the file is 0 bytes or missing, re-run with stderr output visible and fix the error before proceeding to email.

**Page structure**:
1. Cover + Executive Summary (with AIS logo branding)
2. Top 10 Trending Videos (table, engagement color-coded)
3. View Velocity Chart (what's growing fastest right now)
4. Engagement Rate Chart (algorithmic signal)
5. Top Keywords Bar Chart (title vocabulary map)
6. Top Channels Table + Spotlights
7. Transcript Themes (what's actually being taught)
8. Content Opportunity Gaps + Recommended Video Ideas
9. Back Cover (branding + source attribution)

---

## Phase 4 — Delivery

### Step 4.1 — Send Email
```
python tools/send_email.py --attachment .tmp/decks/youtube_trends_YYYY-MM-DD.pdf
```
**Output**: `.tmp/receipts/email_receipt_YYYY-MM-DD.json`

On **first run**, a browser window will open for Gmail OAuth consent. Approve it. The token is saved to `token.json` and subsequent runs will not require browser interaction.

Report the `message_id` and recipient to the user as confirmation.

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Quota exceeded (YouTube 403 `quotaExceeded`) | Stop immediately. Quota resets midnight PT. Re-run the failed step only — `.tmp/` files from completed steps persist. Reduce `results_per_search` in `config.json` if quota is a recurring issue. |
| `YOUTUBE_API_KEY` invalid (403 forbidden) | Halt. Verify the key in Google Cloud Console. Confirm YouTube Data API v3 is enabled on the project. |
| Zero videos returned from search | Warn. Widen `published_within_days` (try 30). Check that search terms are not too narrow or misspelled. |
| All transcripts fail | Note in executive summary. Slides 7 and 8 render with "No transcript data available." Do not halt — the remaining 6 slides are still valuable. |
| `credentials.json` missing for Gmail | Skip Phase 4. Report that the report is available at `.tmp/decks/youtube_trends_YYYY-MM-DD.pdf`. Instruct user to download `credentials.json` from Google Cloud Console with Gmail API enabled. |
| `.pdf` file is 0 bytes | Stop Phase 4. Re-run `build_pdf_report.py` and inspect stderr output. Do not send a broken attachment. |
| Pinned channel ID not found | `fetch_channel_stats.py` logs a warning and continues. Invalid IDs are reported in the output JSON under `invalid_ids`. |
| Gmail OAuth token expired | `send_email.py` will automatically refresh the token using the refresh token. If refresh fails, re-run to trigger a fresh browser consent flow. |

---

## Output Files

| File | Description |
|---|---|
| `.tmp/raw_videos_YYYY-MM-DD.json` | Video stubs from search |
| `.tmp/video_stats_YYYY-MM-DD.json` | Enriched stats per video |
| `.tmp/channel_stats_YYYY-MM-DD.json` | Channel-level data |
| `.tmp/transcripts_YYYY-MM-DD.json` | Transcript text per video |
| `.tmp/analysis_YYYY-MM-DD.json` | Full analytics report with agent-written narrative |
| `.tmp/decks/youtube_trends_YYYY-MM-DD.pdf` | Final deliverable (branded 9-page PDF report) |
| `.tmp/receipts/email_receipt_YYYY-MM-DD.json` | Email delivery confirmation |

All `.tmp/` files are date-stamped and disposable — they can be regenerated by re-running the workflow.

---

## Notes & Lessons Learned
- `youtube-transcript-api` v1.x uses `YouTubeTranscriptApi().fetch(video_id)` (instance method), not the older `YouTubeTranscriptApi.get_transcript()` class method — confirmed 2026-03-23
- Emoji characters in video titles (🧠, 🔥, 🤖) produce harmless matplotlib warnings when rendered in chart labels — these can be ignored
- `search.list` costs 100 quota units per call; with 7 search terms = 700 units per run, well within the 10,000 daily free quota
- `videos.list` batching at 50 IDs per call is very quota-efficient: 93 videos cost only 2 units
