"""
extract_social_signals.py
Finds LinkedIn and Twitter/X profile URLs for a competitor via Serper search.
Does not scrape the profiles directly (login walls). Returns search-derived signals.

Usage:
    python tools/extract_social_signals.py --company "Linear" --domain "linear.app"

Requires:
    SERPER_API_KEY in .env

Output (stdout): JSON dict with keys:
    company, domain, linkedin_url, twitter_url, linkedin_snippet, twitter_snippet
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_SEARCH_URL = "https://google.serper.dev/search"


def search(query: str) -> list[dict]:
    if not SERPER_API_KEY:
        print("ERROR: SERPER_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    try:
        response = requests.post(
            SERPER_SEARCH_URL,
            headers=headers,
            json={"q": query, "num": 5},
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("organic", [])
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return []


def find_profile(results: list[dict], domain_pattern: str) -> tuple[str | None, str | None]:
    """Return (url, snippet) for the first result matching domain_pattern."""
    pattern = re.compile(domain_pattern, re.IGNORECASE)
    for r in results:
        if pattern.search(r.get("link", "")):
            return r.get("link"), r.get("snippet", "")
    return None, None


def extract_social_signals(company: str, domain: str) -> dict:
    result = {
        "company": company,
        "domain": domain,
        "linkedin_url": None,
        "linkedin_snippet": None,
        "twitter_url": None,
        "twitter_snippet": None,
    }

    # LinkedIn company page
    li_results = search(f'site:linkedin.com/company "{company}"')
    li_url, li_snippet = find_profile(li_results, r"linkedin\.com/company/")
    result["linkedin_url"] = li_url
    result["linkedin_snippet"] = li_snippet

    # Twitter / X profile
    tw_results = search(f'site:twitter.com OR site:x.com "{company}" official')
    tw_url, tw_snippet = find_profile(tw_results, r"(twitter\.com|x\.com)/[^/]+$")
    result["twitter_url"] = tw_url
    result["twitter_snippet"] = tw_snippet

    return result


def main():
    parser = argparse.ArgumentParser(description="Find social profiles for a competitor")
    parser.add_argument("--company", required=True, help="Company name (e.g., 'Linear')")
    parser.add_argument("--domain", required=True, help="Company domain (e.g., 'linear.app')")
    args = parser.parse_args()

    result = extract_social_signals(args.company, args.domain)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
