# Workflow: Newsletter Generation (Master)

## Objective
Produce a styled, browser-ready HTML newsletter on a given topic, complete with infographics and optional social media variants, using real-time research from Tavily.

## Required Inputs
| Input | Source |
|---|---|
| `topic` | User prompt |
| `template` | User choice: `default` \| `dark` \| `minimal` (default: `default`) |
| `depth` | Number of search results (default: `8`) |
| `cta_url` | Optional — link for the newsletter's call-to-action button |

## Pre-flight Checks
Before doing anything else:
1. Confirm `.env` contains `TAVILY_API_KEY`. If missing, stop and instruct the user to add it.
2. Confirm `tools/research.py`, `tools/generate_infographic.py`, `tools/generate_html.py` exist.
3. Derive `slug` from the topic (lowercase, hyphens, no special chars). Example: "Future of Remote Work" → `future-of-remote-work`.
4. Set `date_prefix` to today's date in `YYYY-MM-DD` format.

## Step 1 — Research
Run `workflows/research_topic.md` with the provided topic and depth.

Output: `.tmp/research_<slug>.json`

## Step 2 — Outline Approval Gate (PAUSE)
Read the research JSON and present the user with:
- **Proposed headline** (compelling, ~10 words)
- **Proposed sections** (3–5 titles with one-sentence description each)
- **Infographic plan** (which renderer type for each — stat_callout / comparison / timeline / process_steps / quote_card — and what data it will visualize)
- **Proposed CTA** (button text + URL if provided)

**Wait for user approval before continuing.** If the user requests changes, update the plan and confirm again.

## Step 3 — Generate Infographics
Once the outline is approved, run `workflows/generate_infographics.md`.

Output: `.tmp/infographics/<slug>/` containing one `.svg` per infographic.

## Step 4 — Assemble Newsletter
Run `workflows/assemble_newsletter.md` using the approved outline.

Output: `.tmp/content_<slug>.json` and `.tmp/newsletters/<date_prefix>_<slug>.html`

## Step 5 — Preview
```bash
cd NewsLetterDemo
python tools/preview_newsletter.py --html .tmp/newsletters/<date_prefix>_<slug>.html
```
Report the file path to the user and confirm it opened.

## Step 6 — Archive
Copy the following to `archive/<date_prefix>_<slug>/`:
- `.tmp/research_<slug>.json`
- `.tmp/content_<slug>.json`
- `.tmp/newsletters/<date_prefix>_<slug>.html`
- `.tmp/infographics/<slug>/` (all SVGs)

## Step 7 — Social Variants (Optional)
If the content JSON includes `social_variants`, save them:
- `archive/<date_prefix>_<slug>/twitter_thread.txt`
- `archive/<date_prefix>_<slug>/linkedin_post.txt`

## Step 8 — Delivery (Optional)
If the user wants to send the newsletter, run `workflows/deliver_newsletter.md`.

## Error Handling
| Error | Response |
|---|---|
| `TAVILY_API_KEY` missing | Stop, instruct user to add key to `.env` |
| Research returns < 3 sources | Warn user, proceed with caveat |
| SVG generation fails | Log the error, skip that infographic, continue |
| `premailer` import fails | Proceed without CSS inlining (fine for browser preview) |
| HTML generation fails | Stop, report error, do not deliver |

## Outputs
| File | Description |
|---|---|
| `.tmp/research_<slug>.json` | Raw research data |
| `.tmp/content_<slug>.json` | Structured newsletter content |
| `.tmp/newsletters/<date>_<slug>.html` | Final newsletter HTML |
| `.tmp/infographics/<slug>/*.svg` | Infographic SVGs |
| `archive/<date>_<slug>/` | Permanent archive of this issue |
