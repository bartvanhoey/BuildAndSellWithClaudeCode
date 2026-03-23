"""
analyze_trends.py
Processes raw data files to produce a structured analytics report with derived metrics.

Usage:
    python tools/analyze_trends.py
    python tools/analyze_trends.py --date 2026-03-23

Reads:
    .tmp/video_stats_YYYY-MM-DD.json
    .tmp/channel_stats_YYYY-MM-DD.json
    .tmp/transcripts_YYYY-MM-DD.json
    config.json

Output (stdout): JSON summary
Writes: .tmp/analysis_YYYY-MM-DD.json

Note: executive_summary, channel_spotlights, and recommendations are left empty.
The agent fills these in (Phase 2 of the workflow) before running build_slide_deck.py.
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")

# Stop words to exclude from keyword frequency
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "through", "during", "before",
    "after", "above", "below", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "shall", "can", "i", "you", "he", "she", "it", "we",
    "they", "this", "that", "these", "those", "my", "your", "his", "her", "its",
    "our", "their", "what", "which", "who", "when", "where", "why", "how",
    # YouTube-specific noise
    "video", "watch", "youtube", "channel", "subscribe", "like", "comment",
    "full", "new", "2024", "2025", "2026", "ep", "episode", "part", "tutorial",
    "guide", "tips", "best", "top", "using", "use", "get", "make", "your", "not",
    "just", "more", "also", "so", "if", "then", "than", "very", "really", "its",
}


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def find_file(pattern: str, target_date: str | None) -> Path | None:
    if target_date:
        p = TMP_DIR / pattern.replace("*", target_date)
        return p if p.exists() else None
    candidates = sorted(TMP_DIR.glob(pattern), reverse=True)
    return candidates[0] if candidates else None


def days_since_publish(published_at: str) -> float:
    """Calculate days since a video was published."""
    if not published_at:
        return 999
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (now - pub).total_seconds() / 86400
        return max(delta, 0.01)
    except Exception:
        return 999


def compute_view_velocity(video: dict) -> float:
    days = days_since_publish(video.get("published_at", ""))
    return round(video.get("view_count", 0) / days, 1)


def compute_engagement_rate(video: dict) -> float:
    views = video.get("view_count", 0)
    if views == 0:
        return 0.0
    likes = video.get("like_count", 0)
    comments = video.get("comment_count", 0)
    return round((likes + comments) / views * 100, 2)


def extract_title_keywords(videos: list[dict]) -> dict[str, int]:
    """Count significant words from all video titles."""
    counter: Counter = Counter()
    for video in videos:
        title = video.get("title", "").lower()
        # Remove non-alphanumeric characters except spaces
        words = re.findall(r"[a-z0-9]+", title)
        for word in words:
            if word not in STOP_WORDS and len(word) > 2:
                counter[word] += 1
    return dict(counter.most_common(25))


def extract_ngrams(text: str, n: int) -> list[tuple[str, ...]]:
    """Extract n-grams from text."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]


def extract_transcript_themes(transcripts: dict) -> list[dict]:
    """Find top 2-gram and 3-gram phrases across all transcripts."""
    bigram_counter: Counter = Counter()
    trigram_counter: Counter = Counter()

    for vid_data in transcripts.values():
        text = vid_data.get("transcript_text", "")
        if not text:
            continue
        for bg in extract_ngrams(text, 2):
            bigram_counter[" ".join(bg)] += 1
        for tg in extract_ngrams(text, 3):
            trigram_counter[" ".join(tg)] += 1

    # Prefer 3-grams, then fill with 2-grams
    themes = []
    seen = set()
    for phrase, count in trigram_counter.most_common(15):
        themes.append({"phrase": phrase, "count": count})
        seen.add(phrase)

    for phrase, count in bigram_counter.most_common(20):
        # Skip if this bigram is a subset of an already-included trigram
        already_covered = any(phrase in t["phrase"] for t in themes)
        if not already_covered and phrase not in seen:
            themes.append({"phrase": phrase, "count": count})
            seen.add(phrase)
        if len(themes) >= 20:
            break

    return sorted(themes, key=lambda x: x["count"], reverse=True)[:20]


def find_content_gaps(transcript_themes: list[dict], keyword_frequency: dict[str, int]) -> list[str]:
    """
    Find transcript phrases that are discussed frequently but rarely appear in video titles.
    These are potential underserved topics — content opportunities.
    """
    title_words = set(keyword_frequency.keys())
    gaps = []
    for theme in transcript_themes:
        phrase = theme["phrase"]
        phrase_words = set(re.findall(r"[a-z0-9]+", phrase))
        # Gap = none of the phrase words appear in the top title keywords
        overlap = phrase_words & title_words
        if not overlap:
            gaps.append(phrase)
        if len(gaps) >= 10:
            break
    return gaps


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def main():
    parser = argparse.ArgumentParser(description="Analyze collected YouTube data and produce a trends report")
    parser.add_argument("--date", help="Date label YYYY-MM-DD (default: most recent)")
    args = parser.parse_args()

    config = load_config()
    target_date = args.date

    # Load video stats
    video_stats_path = find_file("video_stats_*.json", target_date)
    if not video_stats_path or not video_stats_path.exists():
        print("ERROR: No video_stats_*.json found in .tmp/ — run fetch_video_stats.py first", file=sys.stderr)
        sys.exit(1)
    run_date = video_stats_path.stem.replace("video_stats_", "") or date.today().isoformat()
    videos = json.loads(video_stats_path.read_text(encoding="utf-8"))

    # Load channel stats
    channel_stats_path = find_file("channel_stats_*.json", target_date)
    channels: dict = {}
    if channel_stats_path and channel_stats_path.exists():
        channels = json.loads(channel_stats_path.read_text(encoding="utf-8"))
    else:
        print("WARNING: No channel_stats_*.json found — channel data will be missing.", file=sys.stderr)

    # Load transcripts
    transcripts_path = find_file("transcripts_*.json", target_date)
    transcripts: dict = {}
    if transcripts_path and transcripts_path.exists():
        transcripts = json.loads(transcripts_path.read_text(encoding="utf-8"))
    else:
        print("WARNING: No transcripts_*.json found — transcript analysis will be empty.", file=sys.stderr)

    # Enrich videos with derived metrics
    for video in videos:
        video["view_velocity"] = compute_view_velocity(video)
        video["engagement_rate"] = compute_engagement_rate(video)
        video["url"] = video_url(video["video_id"])

    # Top 10 by view count
    top_videos = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)[:10]

    # Top 15 by view velocity
    view_velocity_ranking = sorted(videos, key=lambda v: v.get("view_velocity", 0), reverse=True)[:15]

    # Top 15 by engagement rate (min 1000 views to filter noise)
    min_views = int(config.get("min_views_threshold", 1000))
    qualified = [v for v in videos if v.get("view_count", 0) >= min_views]
    engagement_ranking = sorted(qualified, key=lambda v: v.get("engagement_rate", 0), reverse=True)[:15]

    # Top channels by total views in dataset
    channel_video_counts: Counter = Counter()
    channel_total_views: Counter = Counter()
    channel_titles: dict[str, str] = {}
    channel_top_video: dict[str, dict] = {}

    for video in videos:
        cid = video.get("channel_id", "")
        if not cid:
            continue
        channel_video_counts[cid] += 1
        channel_total_views[cid] += video.get("view_count", 0)
        channel_titles[cid] = video.get("channel_title", "")
        # Track top video per channel
        existing = channel_top_video.get(cid)
        if existing is None or video.get("view_count", 0) > existing.get("view_count", 0):
            channel_top_video[cid] = video

    top_channels = []
    for cid, total_views in channel_total_views.most_common(10):
        channel_info = channels.get(cid, {})
        video_count_in_dataset = channel_video_counts[cid]
        avg_views = total_views // max(video_count_in_dataset, 1)
        top_vid = channel_top_video.get(cid, {})
        top_channels.append({
            "channel_id": cid,
            "title": channel_info.get("title") or channel_titles.get(cid, ""),
            "subscriber_count": channel_info.get("subscriber_count", 0),
            "videos_in_dataset": video_count_in_dataset,
            "total_views_in_dataset": total_views,
            "avg_views_per_video": avg_views,
            "top_video_title": top_vid.get("title", ""),
            "top_video_url": top_vid.get("url", ""),
        })

    # Keyword frequency from titles
    keyword_frequency = extract_title_keywords(videos)

    # Transcript themes
    transcript_themes = extract_transcript_themes(transcripts)

    # Content gaps
    content_gaps = find_content_gaps(transcript_themes, keyword_frequency)

    # Fastest growing video summary for reporting
    fastest = view_velocity_ranking[0] if view_velocity_ranking else {}

    analysis = {
        "generated_date": run_date,
        "period_days": int(config.get("published_within_days", 14)),
        "total_videos_analyzed": len(videos),
        "total_channels_analyzed": len(channels),
        "fastest_growing_video": {
            "title": fastest.get("title", ""),
            "channel": fastest.get("channel_title", ""),
            "view_velocity": fastest.get("view_velocity", 0),
            "url": fastest.get("url", ""),
        },
        "top_videos": top_videos,
        "view_velocity_ranking": view_velocity_ranking,
        "engagement_ranking": engagement_ranking,
        "top_channels": top_channels,
        "keyword_frequency": keyword_frequency,
        "transcript_themes": transcript_themes,
        "content_gaps": content_gaps,
        # Agent fills these in (Phase 2 of workflow) before running build_slide_deck.py
        "executive_summary": "",
        "channel_spotlights": [],
        "recommendations": [],
    }

    TMP_DIR.mkdir(exist_ok=True)
    output_path = TMP_DIR / f"analysis_{run_date}.json"
    output_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "date": run_date,
        "total_videos": len(videos),
        "top_keyword": next(iter(keyword_frequency), ""),
        "content_gaps_found": len(content_gaps),
        "transcript_themes_found": len(transcript_themes),
        "output": str(output_path),
    }, indent=2))


if __name__ == "__main__":
    main()
