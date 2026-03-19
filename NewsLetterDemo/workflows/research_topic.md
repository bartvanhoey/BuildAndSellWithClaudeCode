# Workflow: Research Topic

## Objective
Use Tavily to research a topic and produce a structured JSON file containing a summary, key points, statistics, and sourced references.

## Required Inputs
| Input | Default |
|---|---|
| `topic` | (required) |
| `depth` | `8` |
| `output_path` | `.tmp/research_<slug>.json` |

## Steps

### 1. Run the research tool
```bash
cd NewsLetterDemo
python tools/research.py \
  --topic "<topic>" \
  --depth <depth> \
  --output <output_path>
```

### 2. Verify output quality
Read the output JSON and check:
- `sources` array has at least 3 entries
- `key_points` array has at least 3 entries
- `summary` is non-empty

If any check fails:
- **< 3 sources**: Re-run with `--depth 12` and broader query phrasing
- **Empty summary**: Proceed with key_points only; note the limitation
- **Empty key_points**: Extract them manually from the top 3 source snippets

### 3. Filter irrelevant sources
Review `sources` and remove any that are:
- Paywalled without accessible content
- Clearly off-topic (wrong industry, wrong time period)
- Duplicate content from the same publication

Update the JSON in-place if filtering is needed (edit the file directly).

### 4. Report
Return to the calling workflow with:
- Path to the research JSON
- Source count
- Key point count
- Any quality issues encountered

## Output JSON Schema
```json
{
  "topic": "string",
  "slug": "string",
  "summary": "string",
  "key_points": ["string"],
  "sources": [{ "title": "string", "url": "string", "snippet": "string", "score": 0.0 }],
  "stats": ["string"],
  "generated_at": "ISO8601"
}
```

## Notes
- Tavily `advanced` search depth is used by default — it costs 2 credits per query instead of 1, but returns significantly higher quality results.
- The free Tavily tier allows 1,000 credits/month.
- `stats` are extracted via regex — they are raw strings and may need cleanup before use in infographic specs.
