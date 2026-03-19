"""
scrape_page.py
Fetches a URL and extracts structured content using BeautifulSoup + lxml.

Usage:
    python tools/scrape_page.py --url "https://example.com/pricing"
    python tools/scrape_page.py --url "https://example.com" --mode messaging

Modes:
    full      - title, meta desc, H1-H3, all paragraphs, links (default)
    messaging - title, meta desc, H1, first 3 paragraphs, CTAs (for homepage analysis)
    pricing   - all text content, focused on price/plan keywords

Output (stdout): JSON dict or {"error": "..."} on failure
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 15


def fetch_page(url: str) -> tuple[str | None, int | None]:
    """Fetch a URL and return (html_text, status_code). Returns (None, code) on error."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code in (403, 429, 503):
            return None, response.status_code
        response.raise_for_status()
        return response.text, response.status_code
    except requests.exceptions.Timeout:
        return None, -1
    except requests.exceptions.RequestException:
        return None, -2


def extract_ctas(soup: BeautifulSoup) -> list[str]:
    """Find button and prominent link text that look like CTAs."""
    ctas = []
    cta_keywords = re.compile(
        r"(get started|sign up|try|free|start|demo|book|schedule|contact|buy|upgrade|plan)",
        re.IGNORECASE,
    )
    for tag in soup.find_all(["a", "button"]):
        text = tag.get_text(strip=True)
        if text and cta_keywords.search(text) and len(text) < 80:
            ctas.append(text)
    return list(dict.fromkeys(ctas))[:10]  # dedupe, cap at 10


def scrape(url: str, mode: str = "full") -> dict:
    html, status = fetch_page(url)

    if html is None:
        error_map = {403: "blocked_403", 429: "blocked_429", 503: "unavailable_503",
                     -1: "timeout", -2: "request_error"}
        return {"error": error_map.get(status, f"http_{status}"), "url": url}

    soup = BeautifulSoup(html, "lxml")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        meta_desc = meta_tag.get("content", "")

    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
    h3s = [h.get_text(strip=True) for h in soup.find_all("h3")]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 30]

    result = {
        "url": url,
        "status_code": status,
        "title": title,
        "meta_description": meta_desc,
        "h1": h1s,
    }

    if mode == "messaging":
        result.update({
            "h2": h2s[:5],
            "paragraphs": paragraphs[:3],
            "ctas": extract_ctas(soup),
        })

    elif mode == "pricing":
        # Grab all visible text, filter to lines mentioning prices/plans
        all_text = soup.get_text(separator="\n")
        price_lines = [
            line.strip() for line in all_text.splitlines()
            if line.strip() and re.search(
                r"(\$|€|£|per month|per year|\/mo|\/yr|free|starter|pro|enterprise|plan|pricing|price)",
                line, re.IGNORECASE
            )
        ]
        result.update({
            "h2": h2s[:8],
            "paragraphs": paragraphs[:5],
            "pricing_text": price_lines[:50],
        })

    else:  # full
        result.update({
            "h2": h2s,
            "h3": h3s[:10],
            "paragraphs": paragraphs[:10],
            "ctas": extract_ctas(soup),
        })

    return result


def main():
    parser = argparse.ArgumentParser(description="Scrape a web page")
    parser.add_argument("--url", required=True, help="URL to scrape")
    parser.add_argument(
        "--mode",
        choices=["full", "messaging", "pricing"],
        default="full",
        help="Extraction mode (default: full)",
    )
    args = parser.parse_args()

    result = scrape(args.url, args.mode)
    sys.stdout.buffer.write((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
