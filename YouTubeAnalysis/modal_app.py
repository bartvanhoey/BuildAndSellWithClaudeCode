"""
modal_app.py
YouTube Analysis workflow deployed to Modal.
Runs every Wednesday at 11:00 AM UTC.

Secrets required (set via: modal secret create youtube-analysis-secrets ...):
    YOUTUBE_API_KEY         - YouTube Data API v3 key
    GMAIL_SENDER            - Gmail address used to send the report
    GMAIL_TOKEN_JSON        - Full contents of token.json (OAuth refresh token)
    GMAIL_CREDENTIALS_JSON  - Full contents of credentials.json (OAuth client secret)

Deploy:   modal deploy modal_app.py
Run now:  modal run modal_app.py
"""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Image: install all dependencies and copy the local project files
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir(".", remote_path="/app")
)

# ---------------------------------------------------------------------------
# App definition
# ---------------------------------------------------------------------------
app = modal.App("youtube-analysis", image=image)

# ---------------------------------------------------------------------------
# Helper: run a tool script and raise on failure
# ---------------------------------------------------------------------------
def run(script: str, *args: str) -> None:
    cmd = [sys.executable, script, *args]
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd="/app")
    if result.returncode != 0:
        raise RuntimeError(f"{script} exited with code {result.returncode}")


# ---------------------------------------------------------------------------
# Scheduled function — every Wednesday at 11:00 AM UTC
# ---------------------------------------------------------------------------
@app.function(
    schedule=modal.Cron("0 11 * * 3"),
    secrets=[modal.Secret.from_name("youtube-analysis-secrets")],
    timeout=600,
)
def run_weekly_analysis():
    today = date.today().isoformat()
    print(f"=== YouTube Analysis — {today} ===")

    # Write OAuth files so the tool scripts can find them
    token_json = os.environ.get("GMAIL_TOKEN_JSON", "")
    credentials_json = os.environ.get("GMAIL_CREDENTIALS_JSON", "")

    token_path = Path("/app/token.json")
    credentials_path = Path("/app/credentials.json")

    if token_json:
        token_path.write_text(token_json, encoding="utf-8")
    if credentials_json:
        credentials_path.write_text(credentials_json, encoding="utf-8")

    # Write .env so tools can load it via python-dotenv
    env_path = Path("/app/.env")
    env_path.write_text(
        f"YOUTUBE_API_KEY={os.environ['YOUTUBE_API_KEY']}\n"
        f"GMAIL_SENDER={os.environ['GMAIL_SENDER']}\n",
        encoding="utf-8",
    )

    # Ensure output directories exist
    Path("/app/.tmp/decks").mkdir(parents=True, exist_ok=True)
    Path("/app/.tmp/receipts").mkdir(parents=True, exist_ok=True)

    # Phase 1: Collect data
    run("tools/fetch_trending_videos.py")
    run("tools/fetch_video_stats.py")
    run("tools/fetch_channel_stats.py")
    run("tools/fetch_transcripts.py")

    # Phase 2: Analyze
    run("tools/analyze_trends.py")

    # Phase 3: Build PDF report
    run("tools/build_pdf_report.py")

    # Phase 4: Send email
    pdf_path = f".tmp/decks/youtube_trends_{today}.pdf"
    run("tools/send_email.py", "--attachment", pdf_path)

    print(f"\n=== Done. Report sent for {today} ===")


# ---------------------------------------------------------------------------
# Local entrypoint for manual one-off runs: modal run modal_app.py
# ---------------------------------------------------------------------------
@app.local_entrypoint()
def main():
    run_weekly_analysis.remote()
