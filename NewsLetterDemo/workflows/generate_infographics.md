# Workflow: Generate Infographics

## Objective
Turn an approved outline and research JSON into rendered SVG infographic files, one per planned infographic.

## Required Inputs
| Input | Source |
|---|---|
| `research_json_path` | Output of `research_topic.md` |
| `approved_outline` | Approved in Step 2 of master workflow |
| `slug` | Derived from topic |

## Renderer Reference
| Type | Best for |
|---|---|
| `stat_callout` | Single striking number (%, $, count) with supporting label |
| `comparison` | Two things side by side (before/after, old/new, two options) |
| `timeline` | Chronological events (4–6 points) |
| `process_steps` | Sequential steps (2–5 steps) |
| `quote_card` | Attributed quote from a source |

## Steps

### 1. Write spec JSON files
For each infographic in the approved outline, write a spec JSON to `.tmp/infographic_specs/<slug>/<name>.json`.

**stat_callout spec:**
```json
{
  "type": "stat_callout",
  "value": "73%",
  "label": "of enterprises plan to increase AI investment in 2026",
  "context": "Source: Gartner, 2025",
  "accent": "#2563eb"
}
```

**comparison spec:**
```json
{
  "type": "comparison",
  "title": "Remote vs. In-Office Productivity",
  "left":  { "label": "Remote",  "value": "+13%", "description": "Output increase vs. office baseline" },
  "right": { "label": "In-Office", "value": "Baseline", "description": "Pre-pandemic office productivity" },
  "accent_left": "#2563eb",
  "accent_right": "#059669"
}
```

**timeline spec:**
```json
{
  "type": "timeline",
  "title": "Remote Work Milestones",
  "events": [
    { "year": "2020", "label": "COVID-19 forces global shift" },
    { "year": "2021", "label": "Hybrid models emerge" },
    { "year": "2023", "label": "RTO mandates spread" },
    { "year": "2025", "label": "Async-first companies scale" }
  ],
  "accent": "#7c3aed"
}
```

**process_steps spec:**
```json
{
  "type": "process_steps",
  "title": "How to Build a Remote-First Culture",
  "steps": [
    { "title": "Document everything", "description": "Default to writing, not meetings" },
    { "title": "Async by default", "description": "Reserve sync time for decisions only" },
    { "title": "Measure output", "description": "Track deliverables, not hours" }
  ],
  "accent": "#2563eb"
}
```

**quote_card spec:**
```json
{
  "type": "quote_card",
  "quote": "The future of work is not a place — it's a practice.",
  "attribution": "Dr. Sarah Chen, Future of Work Institute",
  "accent": "#2563eb"
}
```

### 2. Render each spec to SVG
For each spec file:
```bash
cd NewsLetterDemo
python tools/generate_infographic.py \
  --spec .tmp/infographic_specs/<slug>/<name>.json \
  --output .tmp/infographics/<slug>/<name>.svg
```

### 3. Verify renders
Check that each `.svg` file was created and is non-empty. If a render fails:
- Read the error message
- Fix the spec JSON (common issues: missing required keys, invalid color format)
- Re-run that single spec

### 4. Report
Return to calling workflow with a mapping of `infographic name → svg path` for use in the content JSON.

## Accent Color Guide
Match infographic accent to the newsletter template using brand colors:

| Template | Primary accent | Secondary / contrast |
|---|---|---|
| `default` | `#093824` (brand green) | `#c0652a` (terracotta) |
| `dark` | `#7fb9a6` (primary-300, readable on dark) | `#d99773` (secondary-300) |
| `minimal` | `#093824` (brand green) | `#c0652a` (terracotta) |

For **comparison** infographics, use `accent_left: "#093824"` and `accent_right: "#c0652a"` to contrast green vs. terracotta.

Use the brand green as the default for all infographics unless the content specifically calls for warm/secondary tones (e.g., a warning, a human-interest story, a quote card).
