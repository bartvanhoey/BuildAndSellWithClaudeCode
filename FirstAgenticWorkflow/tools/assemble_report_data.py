"""
assemble_report_data.py
Merges Claude-constructed report_data JSON into a dated file in .tmp/.

Claude builds the full report_data dict in memory and passes it via stdin (or --file).
This tool validates the schema, stamps the date, and writes .tmp/report_data_YYYY-MM-DD.json.

Usage:
    echo '<json>' | python tools/assemble_report_data.py
    python tools/assemble_report_data.py --file /path/to/draft.json

Expected input schema:
{
  "company": { ...company_profile fields... },
  "generated_date": "YYYY-MM-DD",
  "executive_summary": "Claude-written prose...",
  "competitors": [
    {
      "name": "CompetitorName",
      "domain": "example.com",
      "pricing": { "raw_text": [...], "search_results": [...], "notes": "..." },
      "messaging": { "h1": [...], "meta_description": "...", "ctas": [...], "notes": "..." },
      "seo": { "search_results": [...], "notes": "..." },
      "news": [ { "title": "...", "link": "...", "date": "...", "source": "..." } ],
      "social": { "linkedin_url": "...", "twitter_url": "..." },
      "scrape_errors": []
    }
  ]
}

Output: .tmp/report_data_YYYY-MM-DD.json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"

REQUIRED_TOP_KEYS = {"company", "executive_summary", "competitors"}
REQUIRED_COMPETITOR_KEYS = {"name", "domain"}


def validate(data: dict) -> list[str]:
    errors = []
    missing_top = REQUIRED_TOP_KEYS - set(data.keys())
    if missing_top:
        errors.append(f"Missing top-level keys: {missing_top}")

    competitors = data.get("competitors", [])
    if not isinstance(competitors, list):
        errors.append("'competitors' must be a list")
    else:
        for i, c in enumerate(competitors):
            missing = REQUIRED_COMPETITOR_KEYS - set(c.keys())
            if missing:
                errors.append(f"Competitor[{i}] missing keys: {missing}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Assemble and persist report data JSON")
    parser.add_argument("--file", help="Path to JSON file (default: read from stdin)")
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate(data)
    if errors:
        for err in errors:
            print(f"VALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    # Stamp date if not present
    today = date.today().isoformat()
    data.setdefault("generated_date", today)

    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"report_data_{today}.json"
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"status": "ok", "output": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
