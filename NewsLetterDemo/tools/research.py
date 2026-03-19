"""
research.py — Tavily-powered topic research tool

CLI: python research.py --topic "AI in healthcare" --depth 8 --output .tmp/research_ai-in-healthcare.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


def slugify(text: str) -> str:
    """Convert a topic string to a URL-safe slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def search_topic(client: TavilyClient, topic: str, num_results: int) -> dict:
    """Call Tavily search and return raw response."""
    response = client.search(
        query=topic,
        search_depth="advanced",
        max_results=num_results,
        include_answer=True,
        include_raw_content=False,
    )
    return response


def extract_stats(results: list[dict]) -> list[str]:
    """Pull numeric facts from result snippets via regex."""
    stats = []
    # Must start with a currency symbol or digit, and contain a unit/qualifier
    stat_pattern = re.compile(
        r"[\$€£]?\d[\d,\.]*\s*(?:billion|million|trillion|thousand|%|percent)\b(?:\s+\w+){0,8}",
        re.IGNORECASE,
    )
    seen = set()
    for result in results:
        text = result.get("content", "") or result.get("snippet", "")
        matches = stat_pattern.findall(text)
        for match in matches:
            clean = match.strip().rstrip(".,;:")
            if 8 < len(clean) < 120 and clean.lower() not in seen:
                seen.add(clean.lower())
                stats.append(clean)
                if len(stats) >= 15:
                    return stats
    return stats


def deduplicate_sources(results: list[dict]) -> list[dict]:
    """Remove duplicate domains, keeping the highest-scored result per domain."""
    seen_domains = {}
    for result in results:
        url = result.get("url", "")
        try:
            domain = re.search(r"https?://(?:www\.)?([^/]+)", url).group(1)
        except (AttributeError, IndexError):
            domain = url
        score = result.get("score", 0)
        if domain not in seen_domains or score > seen_domains[domain]["score"]:
            seen_domains[domain] = {"score": score, "result": result}
    return [v["result"] for v in seen_domains.values()]


def build_key_points(answer: str, results: list[dict]) -> list[str]:
    """Extract key points from the Tavily answer summary and top snippets."""
    key_points = []

    # Split the answer into sentences
    if answer:
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 40:
                key_points.append(sentence)
            if len(key_points) >= 5:
                break

    # Supplement from top result snippets if needed
    for result in results[:3]:
        if len(key_points) >= 8:
            break
        snippet = (result.get("content", "") or "").strip()
        if snippet and len(snippet) > 60:
            # Take just first sentence
            first = re.split(r"(?<=[.!?])\s+", snippet)[0]
            if first not in key_points and len(first) > 40:
                key_points.append(first)

    return key_points


def save_research(data: dict, output_path: str) -> Path:
    """Write structured JSON to the output path, creating dirs as needed."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def run_research(topic: str, depth: int, output: str) -> dict:
    """Full research pipeline: search → extract → dedupe → save."""
    import os

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("ERROR: TAVILY_API_KEY not found in environment / .env file", file=sys.stderr)
        sys.exit(1)

    client = TavilyClient(api_key=api_key)

    print(f"Searching Tavily for: {topic!r} (depth={depth})...")
    response = search_topic(client, topic, depth)

    raw_results = response.get("results", [])
    answer = response.get("answer", "")

    deduped = deduplicate_sources(raw_results)
    stats = extract_stats(deduped)
    key_points = build_key_points(answer, deduped)

    sources = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content", "") or "")[:300],
            "score": round(r.get("score", 0), 4),
        }
        for r in deduped
    ]

    data = {
        "topic": topic,
        "slug": slugify(topic),
        "summary": answer,
        "key_points": key_points,
        "sources": sources,
        "stats": stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    path = save_research(data, output)
    print(f"Research saved to: {path}")
    print(f"  Sources: {len(sources)}  |  Key points: {len(key_points)}  |  Stats: {len(stats)}")
    return data


def main():
    parser = argparse.ArgumentParser(description="Research a topic using Tavily and save structured JSON.")
    parser.add_argument("--topic", required=True, help="Topic to research")
    parser.add_argument("--depth", type=int, default=8, help="Number of search results (default: 8)")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    args = parser.parse_args()
    run_research(args.topic, args.depth, args.output)


if __name__ == "__main__":
    main()
