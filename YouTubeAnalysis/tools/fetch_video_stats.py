"""
fetch_video_stats.py
Fetches detailed statistics for a list of YouTube video IDs.

Usage:
    python tools/fetch_video_stats.py
    python tools/fetch_video_stats.py --input .tmp/raw_videos_2026-03-23.json
    python tools/fetch_video_stats.py --date 2026-03-23

Reads:
    .tmp/raw_videos_YYYY-MM-DD.json  (from fetch_trending_videos.py)
    .env                              (YOUTUBE_API_KEY)

Output (stdout): JSON summary
Writes: .tmp/video_stats_YYYY-MM-DD.json

Quota cost: ceil(len(video_ids) / 50) units — very cheap
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

import os

load_dotenv(PROJECT_ROOT / ".env")

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "ERROR: google-api-python-client not installed.\n"
        "Run: pip install google-api-python-client",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_iso8601_duration(duration: str) -> int:
    """Convert ISO 8601 duration (e.g. PT4M32S) to total seconds."""
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def find_raw_videos(target_date: str | None) -> Path:
    if target_date:
        p = TMP_DIR / f"raw_videos_{target_date}.json"
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)
        return p
    candidates = sorted(TMP_DIR.glob("raw_videos_*.json"), reverse=True)
    if not candidates:
        print("ERROR: No raw_videos_*.json found in .tmp/ — run fetch_trending_videos.py first", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def fetch_stats_batch(youtube, video_ids: list[str]) -> list[dict]:
    """Fetch stats for up to 50 video IDs in one API call."""
    try:
        response = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids),
        ).execute()
    except HttpError as e:
        error_content = json.loads(e.content.decode())
        reason = error_content.get("error", {}).get("errors", [{}])[0].get("reason", "unknown")
        if reason == "quotaExceeded":
            print(
                "ERROR: YouTube API quota exceeded. Quota resets at midnight PT.",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: YouTube API error: {e}", file=sys.stderr)
        sys.exit(1)

    results = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        duration_iso = content.get("duration", "PT0S")
        results.append({
            "video_id": item["id"],
            "title": snippet.get("title", ""),
            "channel_id": snippet.get("channelId", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "description_snippet": snippet.get("description", "")[:300],
            "tags": snippet.get("tags", []),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_iso": duration_iso,
            "duration_seconds": parse_iso8601_duration(duration_iso),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch video statistics for collected video IDs")
    parser.add_argument("--input", help="Path to raw_videos JSON (overrides --date)")
    parser.add_argument("--date", help="Date label YYYY-MM-DD (default: most recent)")
    args = parser.parse_args()

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    if args.input:
        raw_path = Path(args.input)
        if not raw_path.exists():
            print(f"ERROR: {raw_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        raw_path = find_raw_videos(args.date)

    # Infer date from filename
    run_date = raw_path.stem.replace("raw_videos_", "") or date.today().isoformat()

    raw_stubs = json.loads(raw_path.read_text(encoding="utf-8"))
    # Build lookup: video_id -> search_term
    search_term_map = {stub["video_id"]: stub.get("search_term", "") for stub in raw_stubs}
    video_ids = list(search_term_map.keys())

    if not video_ids:
        print("ERROR: No video IDs found in input file.", file=sys.stderr)
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=api_key)

    enriched = []
    batch_size = 50
    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i:i + batch_size]
        print(f"  Fetching stats batch {i // batch_size + 1} ({len(batch)} videos)...", file=sys.stderr)
        batch_results = fetch_stats_batch(youtube, batch)
        for result in batch_results:
            result["search_term"] = search_term_map.get(result["video_id"], "")
            enriched.append(result)

    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"video_stats_{run_date}.json"
    output_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "date": run_date,
        "videos_fetched": len(enriched),
        "output": str(output_path),
    }, indent=2))


if __name__ == "__main__":
    main()
