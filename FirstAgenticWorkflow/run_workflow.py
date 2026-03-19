"""
run_workflow.py
Unattended entry point for Windows Task Scheduler.
Reads the competitor_analysis workflow SOP and runs it via the Anthropic SDK.

Usage:
    python run_workflow.py

Schedule (Windows Task Scheduler):
    Program:   python.exe  (full path to your venv python, e.g. C:\\...\\venv\\Scripts\\python.exe)
    Arguments: C:\\path\\to\\FirstAgenticWorkflow\\run_workflow.py
    Start in:  C:\\path\\to\\FirstAgenticWorkflow
    Trigger:   Weekly, Monday 07:00 AM
    Setting:   Run task as soon as possible after a scheduled start is missed

Requires:
    ANTHROPIC_API_KEY in .env
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

WORKFLOW_FILE = PROJECT_ROOT / "workflows" / "competitor_analysis.md"
PROFILE_FILE = PROJECT_ROOT / "company_profile.json"
LOG_DIR = PROJECT_ROOT / ".tmp"


def load_workflow() -> str:
    if not WORKFLOW_FILE.exists():
        print(f"ERROR: Workflow file not found: {WORKFLOW_FILE}", file=sys.stderr)
        sys.exit(1)
    return WORKFLOW_FILE.read_text(encoding="utf-8")


def load_profile() -> dict:
    if not PROFILE_FILE.exists():
        return {}
    text = PROFILE_FILE.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def build_prompt(workflow: str, profile: dict) -> str:
    today = date.today().isoformat()
    profile_json = json.dumps(profile, indent=2)

    return f"""Today is {today}. You are running the weekly competitor analysis workflow.

## Company Profile
```json
{profile_json}
```

## Workflow Instructions
{workflow}

---

Execute the full workflow from Phase 0 through Phase 7. Work through each phase sequentially.
Use the tools described in each phase by running the corresponding Python scripts from the
`tools/` directory. After completing the workflow, provide:
1. The Google Drive shareable link (or local PDF path if upload was skipped)
2. A brief summary of key findings
3. Any competitors that had scrape errors and need manual review

If `company_profile.json` is empty or missing `company_name`, halt immediately and output:
"SETUP REQUIRED: Please run workflows/onboarding.md to configure your company profile before running the analysis."
"""


def run():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    workflow = load_workflow()
    profile = load_profile()

    if not profile.get("company_name"):
        print(
            "SETUP REQUIRED: company_profile.json is empty.\n"
            "Run workflows/onboarding.md to configure your company profile.",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = build_prompt(workflow, profile)

    client = anthropic.Anthropic(api_key=api_key)

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"run_log_{date.today().isoformat()}.txt"

    print(f"Starting competitor analysis for {profile.get('company_name')} on {date.today().isoformat()}")
    print(f"Log: {log_path}")

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"Run started: {date.today().isoformat()}\n")
        log_file.write(f"Company: {profile.get('company_name')}\n\n")

        # Stream the response so Task Scheduler can capture stdout
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                log_file.write(text)

        print()  # newline after stream
        log_file.write("\n\nRun completed.\n")

    print(f"\nRun complete. Full log saved to: {log_path}")


if __name__ == "__main__":
    run()
