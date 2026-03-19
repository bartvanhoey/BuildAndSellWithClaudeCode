"""
search_web.py
Serper.dev /search wrapper. Returns top organic results as JSON.

Usage:
    python tools/search_web.py --query "jira alternatives 2024" [--num 10]

Requires:
    SERPER_API_KEY in .env

Output (stdout): JSON array of results, each with keys:
    title, link, snippet, position
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
SERPER_SEARCH_URL = "https://google.serper.dev/search"


def search_web(query: str, num: int = 10) -> list[dict]:
    """
    Run a Google search via Serper and return organic results.

    Args:
        query: Search query string
        num:   Number of results to return (max 100)

    Returns:
        List of result dicts with keys: title, link, snippet, position
    """
    if not SERPER_API_KEY:
        print("ERROR: SERPER_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    payload = {"q": query, "num": num}
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            SERPER_SEARCH_URL,
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
    organic = data.get("organic", [])

    results = []
    for item in organic:
        results.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "position": item.get("position", 0),
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Search the web via Serper")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--num", type=int, default=10, help="Number of results (default: 10)")
    args = parser.parse_args()

    results = search_web(args.query, args.num)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
