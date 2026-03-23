"""
fetch_transcripts.py
Downloads transcripts for the top N videos by view count.

Usage:
    python tools/fetch_transcripts.py
    python tools/fetch_transcripts.py --input .tmp/video_stats_2026-03-23.json
    python tools/fetch_transcripts.py --date 2026-03-23 --max 20

Reads:
    .tmp/video_stats_YYYY-MM-DD.json  (from fetch_video_stats.py)
    config.json                        (max_transcripts)

No API quota cost. Uses youtube-transcript-api (web scraping).

Per-video errors are stored in the output JSON — script never exits non-zero
for individual transcript failures.

Output (stdout): JSON summary
Writes: .tmp/transcripts_YYYY-MM-DD.json — object keyed by video_id
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

load_dotenv(PROJECT_ROOT / ".env")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )
    _YT_API = YouTubeTranscriptApi()
except ImportError:
    print(
        "ERROR: youtube-transcript-api not installed.\n"
        "Run: pip install youtube-transcript-api",
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


def fetch_transcript(video_id: str, title: str) -> dict:
    """Fetch transcript for a single video. Returns a result dict with error key if failed."""
    base = {"video_id": video_id, "title": title}
    try:
        fetched = _YT_API.fetch(video_id, languages=["en", "en-US", "en-GB"])
        text = " ".join(entry.text for entry in fetched)
        return {
            **base,
            "transcript_text": text,
            "word_count": len(text.split()),
            "language": "en",
            "error": None,
        }
    except TranscriptsDisabled:
        return {**base, "transcript_text": "", "word_count": 0, "language": None, "error": "TranscriptsDisabled"}
    except NoTranscriptFound:
        return {**base, "transcript_text": "", "word_count": 0, "language": None, "error": "NoTranscriptFound"}
    except VideoUnavailable:
        return {**base, "transcript_text": "", "word_count": 0, "language": None, "error": "VideoUnavailable"}
    except Exception as e:
        return {**base, "transcript_text": "", "word_count": 0, "language": None, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Fetch transcripts for top videos by view count")
    parser.add_argument("--input", help="Path to video_stats JSON (overrides --date)")
    parser.add_argument("--date", help="Date label YYYY-MM-DD (default: most recent)")
    parser.add_argument("--max", type=int, help="Max number of transcripts to fetch (overrides config)")
    args = parser.parse_args()

    if args.input:
        stats_path = Path(args.input)
        if not stats_path.exists():
            print(f"ERROR: {stats_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        stats_path = find_video_stats(args.date)

    run_date = stats_path.stem.replace("video_stats_", "") or date.today().isoformat()

    config = load_config()
    max_transcripts = args.max or int(config.get("max_transcripts", 20))

    videos = json.loads(stats_path.read_text(encoding="utf-8"))

    # Sort by view count descending, take top N
    sorted_videos = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)
    top_videos = sorted_videos[:max_transcripts]

    results: dict[str, dict] = {}
    success_count = 0
    error_count = 0

    for video in top_videos:
        vid_id = video["video_id"]
        title = video.get("title", "")
        print(f"  Fetching transcript: {title[:60]}...", file=sys.stderr)
        result = fetch_transcript(vid_id, title)
        results[vid_id] = result
        if result["error"] is None:
            success_count += 1
        else:
            error_count += 1
            print(f"    -> {result['error']}", file=sys.stderr)

    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"transcripts_{run_date}.json"
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "date": run_date,
        "transcripts_attempted": len(top_videos),
        "transcripts_success": success_count,
        "transcripts_failed": error_count,
        "output": str(output_path),
    }, indent=2))


if __name__ == "__main__":
    main()
