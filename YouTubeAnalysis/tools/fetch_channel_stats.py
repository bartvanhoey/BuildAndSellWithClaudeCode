"""
fetch_channel_stats.py
Fetches channel-level statistics for all channels found in video stats.

Usage:
    python tools/fetch_channel_stats.py
    python tools/fetch_channel_stats.py --input .tmp/video_stats_2026-03-23.json
    python tools/fetch_channel_stats.py --date 2026-03-23

Reads:
    .tmp/video_stats_YYYY-MM-DD.json  (from fetch_video_stats.py)
    config.json                        (pinned_channels)
    .env                               (YOUTUBE_API_KEY)

Output (stdout): JSON summary
Writes: .tmp/channel_stats_YYYY-MM-DD.json — object keyed by channel_id

Quota cost: ceil(len(unique_channel_ids) / 50) units
"""

import argparse
import json
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


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def find_video_stats(target_date: str | None) -> Path:
    if target_date:
        p = TMP_DIR / f"video_stats_{target_date}.json"
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)
        return p
    candidates = sorted(TMP_DIR.glob("video_stats_*.json"), reverse=True)
    if not candidates:
        print("ERROR: No video_stats_*.json found in .tmp/ — run fetch_video_stats.py first", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def fetch_channels_batch(youtube, channel_ids: list[str]) -> list[dict]:
    """Fetch channel info for up to 50 channel IDs in one API call."""
    try:
        response = youtube.channels().list(
            part="snippet,statistics",
            id=",".join(channel_ids),
        ).execute()
    except HttpError as e:
        error_content = json.loads(e.content.decode())
        reason = error_content.get("error", {}).get("errors", [{}])[0].get("reason", "unknown")
        if reason == "quotaExceeded":
            print("ERROR: YouTube API quota exceeded. Quota resets at midnight PT.", file=sys.stderr)
        else:
            print(f"ERROR: YouTube API error: {e}", file=sys.stderr)
        sys.exit(1)

    results = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )
        results.append({
            "channel_id": item["id"],
            "title": snippet.get("title", ""),
            "description_snippet": snippet.get("description", "")[:200],
            "custom_url": snippet.get("customUrl", ""),
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail_url": thumbnail_url,
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "total_view_count": int(stats.get("viewCount", 0)),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch channel statistics for discovered channels")
    parser.add_argument("--input", help="Path to video_stats JSON (overrides --date)")
    parser.add_argument("--date", help="Date label YYYY-MM-DD (default: most recent)")
    args = parser.parse_args()

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    if args.input:
        stats_path = Path(args.input)
        if not stats_path.exists():
            print(f"ERROR: {stats_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        stats_path = find_video_stats(args.date)

    run_date = stats_path.stem.replace("video_stats_", "") or date.today().isoformat()

    videos = json.loads(stats_path.read_text(encoding="utf-8"))
    config = load_config()

    # Collect unique channel IDs from videos
    channel_ids: set[str] = set()
    for video in videos:
        cid = video.get("channel_id")
        if cid:
            channel_ids.add(cid)

    # Add pinned channels from config
    for cid in config.get("pinned_channels", []):
        if cid:
            channel_ids.add(cid)

    channel_ids_list = list(channel_ids)
    if not channel_ids_list:
        print("ERROR: No channel IDs found.", file=sys.stderr)
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=api_key)

    all_channels: dict[str, dict] = {}
    batch_size = 50
    invalid_ids = []

    for i in range(0, len(channel_ids_list), batch_size):
        batch = channel_ids_list[i:i + batch_size]
        print(f"  Fetching channel batch {i // batch_size + 1} ({len(batch)} channels)...", file=sys.stderr)
        results = fetch_channels_batch(youtube, batch)
        returned_ids = {r["channel_id"] for r in results}
        for cid in batch:
            if cid not in returned_ids:
                invalid_ids.append(cid)
                print(f"  WARNING: Channel ID not found or invalid: {cid}", file=sys.stderr)
        for channel in results:
            all_channels[channel["channel_id"]] = channel

    if invalid_ids:
        print(f"  WARNING: {len(invalid_ids)} channel ID(s) were not found: {invalid_ids}", file=sys.stderr)

    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"channel_stats_{run_date}.json"
    output_path.write_text(json.dumps(all_channels, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "date": run_date,
        "channels_fetched": len(all_channels),
        "invalid_ids": invalid_ids,
        "output": str(output_path),
    }, indent=2))


if __name__ == "__main__":
    main()
