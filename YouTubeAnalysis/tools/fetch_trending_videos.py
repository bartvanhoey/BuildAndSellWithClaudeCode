"""
fetch_trending_videos.py
Searches YouTube for trending videos matching configured keywords.

Usage:
    python tools/fetch_trending_videos.py
    python tools/fetch_trending_videos.py --date 2026-03-23

Reads:
    config.json       (search_terms, results_per_search, published_within_days)
    .env              (YOUTUBE_API_KEY)

Output (stdout): JSON array of deduplicated video stubs
Writes: .tmp/raw_videos_YYYY-MM-DD.json

Quota cost: 100 units × number of search_terms (default: ~700 units for 7 terms)
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
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


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        print("ERROR: config.json not found in project root.", file=sys.stderr)
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def search_videos(youtube, query: str, max_results: int, published_after: str) -> list[dict]:
    """Run a single search.list call and return video stubs."""
    try:
        response = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            order="viewCount",
            publishedAfter=published_after,
            maxResults=max_results,
        ).execute()
    except HttpError as e:
        error_content = json.loads(e.content.decode())
        reason = error_content.get("error", {}).get("errors", [{}])[0].get("reason", "unknown")
        if reason == "quotaExceeded":
            print(
                "ERROR: YouTube API quota exceeded. Quota resets at midnight PT.\n"
                "Re-run after the quota resets or reduce results_per_search in config.json.",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: YouTube API error for query '{query}': {e}", file=sys.stderr)
        sys.exit(1)

    stubs = []
    for item in response.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        stubs.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "channel_id": snippet.get("channelId", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "search_term": query,
        })
    return stubs


def main():
    parser = argparse.ArgumentParser(description="Fetch trending YouTube videos by keyword")
    parser.add_argument("--date", help="Output date label YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    run_date = args.date or date.today().isoformat()

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    search_terms = config.get("search_terms", [])
    if not search_terms:
        print("ERROR: No search_terms defined in config.json", file=sys.stderr)
        sys.exit(1)

    results_per_search = int(config.get("results_per_search", 10))
    published_within_days = int(config.get("published_within_days", 14))

    cutoff = datetime.now(timezone.utc) - timedelta(days=published_within_days)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    youtube = build("youtube", "v3", developerKey=api_key)

    all_stubs: list[dict] = []
    seen_ids: set[str] = set()

    for term in search_terms:
        print(f"  Searching: {term}", file=sys.stderr)
        stubs = search_videos(youtube, term, results_per_search, published_after)
        for stub in stubs:
            if stub["video_id"] not in seen_ids:
                seen_ids.add(stub["video_id"])
                all_stubs.append(stub)

    if len(all_stubs) < 10:
        print(
            f"WARNING: Only {len(all_stubs)} unique videos found. "
            "Consider widening published_within_days in config.json.",
            file=sys.stderr,
        )

    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"raw_videos_{run_date}.json"
    output_path.write_text(json.dumps(all_stubs, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "date": run_date,
        "videos_found": len(all_stubs),
        "search_terms_used": len(search_terms),
        "output": str(output_path),
    }, indent=2))


if __name__ == "__main__":
    main()
