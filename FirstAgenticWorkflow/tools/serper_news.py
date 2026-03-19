"""
serper_news.py
Serper.dev /news wrapper. Returns recent news articles for a query.

Usage:
    python tools/serper_news.py --query "Linear app" [--days 7] [--num 10]

Requires:
    SERPER_API_KEY in .env

Output (stdout): JSON array of articles, each with keys:
    title, link, snippet, source, date
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_NEWS_URL = "https://google.serper.dev/news"


def fetch_news(query: str, num: int = 10) -> list[dict]:
    """
    Fetch recent news for a query via Serper /news.

    Args:
        query: Search query (e.g., competitor name)
        num:   Max articles to return

    Returns:
        List of article dicts: title, link, snippet, source, date
    """
    if not SERPER_API_KEY:
        print("ERROR: SERPER_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    payload = {"q": query, "num": num, "tbs": "qdr:w"}  # qdr:w = past week
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            SERPER_NEWS_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"ERROR: Request timed out for query: {query}", file=sys.stderr)
        return [{"error": "timeout", "query": query}]
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP {e.response.status_code} for query: {query}", file=sys.stderr)
        return [{"error": f"http_{e.response.status_code}", "query": query}]
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed: {e}", file=sys.stderr)
        return [{"error": str(e), "query": query}]

    data = response.json()
    news_items = data.get("news", [])

    results = []
    for item in news_items:
        results.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "source": item.get("source", ""),
            "date": item.get("date", ""),
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch recent news via Serper")
    parser.add_argument("--query", required=True, help="Search query (e.g., company name)")
    parser.add_argument("--num", type=int, default=10, help="Number of articles (default: 10)")
    args = parser.parse_args()

    results = fetch_news(args.query, args.num)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
