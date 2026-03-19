# Workflow: Assemble Newsletter

## Objective
Write compelling newsletter copy from the research JSON and approved outline, produce a content JSON, then render the final HTML using `generate_html.py`.

## Required Inputs
| Input | Source |
|---|---|
| `research_json_path` | Output of `research_topic.md` |
| `approved_outline` | Approved in Step 2 of master workflow |
| `infographic_map` | Output of `generate_infographics.md` (name → svg path) |
| `slug` | Derived from topic |
| `template` | `default` \| `dark` \| `minimal` |
| `cta_url` | Optional |
| `date_prefix` | `YYYY-MM-DD` |

## Steps

### 1. Write newsletter copy
Using the research JSON and approved outline, write:

**Headline** — compelling, ~10 words. Should be a declarative statement or provocative question, not just a topic label.
- Bad: "Remote Work in 2026"
- Good: "Remote Work Is Winning — But the Numbers Tell a Complicated Story"

**Intro** (2–3 paragraphs) — hook the reader, establish stakes, preview what they'll learn.

**Section bodies** — one paragraph (150–250 words) per section. Be specific: use actual statistics from the research, name the companies and people from sources, make concrete claims.

**Conclusion** (1–2 paragraphs) — synthesize the key insight. What should the reader *do* or *think differently* as a result of reading this?

**CTA text** — action-oriented, 5–8 words (e.g., "Explore the full research report" or "Share this with your team").

**Social variants:**
- **Twitter/X thread**: 5 tweets. Tweet 1 = hook + the big finding. Tweets 2–4 = one key point each. Tweet 5 = CTA/opinion.
- **LinkedIn post**: 150–200 words. Professional tone. Start with a bold one-line hook. Use line breaks for readability.

### 2. Build content JSON
Write the content JSON to `.tmp/content_<slug>.json`:

```json
{
  "subject": "email subject line (matches or derives from headline)",
  "headline": "newsletter headline",
  "intro": "paragraph 1\n\nparagraph 2\n\nparagraph 3",
  "sections": [
    {
      "title": "Section Title",
      "body": "paragraph 1\n\nparagraph 2",
      "infographic": ".tmp/infographics/<slug>/<name>.svg"
    }
  ],
  "conclusion": "paragraph 1\n\nparagraph 2",
  "cta": {
    "text": "button text",
    "url": "https://..."
  },
  "social_variants": {
    "twitter": "Tweet 1/5: ...\n\nTweet 2/5: ...",
    "linkedin": "full linkedin post text"
  },
  "sources": [
    { "title": "Source Title", "url": "https://..." }
  ]
}
```

Notes:
- Set `"infographic"` to `null` for sections without an infographic
- Include all sources from the research JSON (up to 8)
- Use `\n\n` to separate paragraphs within multi-paragraph fields

### 3. Render HTML
```bash
cd NewsLetterDemo
python tools/generate_html.py \
  --content .tmp/content_<slug>.json \
  --template <template> \
  --output .tmp/newsletters/<date_prefix>_<slug>.html
```

Add `--inline-css` if sending via email (requires `premailer`).

### 4. Verify output
- HTML file exists and is > 5KB
- Open in browser mentally: sections render in order, infographics appear inline, CTA button is visible

### 5. Report
Return to calling workflow with:
- Path to content JSON
- Path to HTML file
- Section count
- Whether social variants were included

## Writing Quality Standards
- **Specific over vague**: "53% of knowledge workers" beats "many workers"
- **Active voice**: "Companies are abandoning RTO mandates" beats "RTO mandates are being abandoned"
- **One idea per paragraph**: Don't stack multiple claims — give each room to breathe
- **No filler phrases**: Avoid "In conclusion", "It's worth noting", "Needless to say"
