"""
Scrape DailyRemote job listings for a given search term and location.
Outputs results to an Excel file.

Usage (from AgenticWorkflowDemo/ directory):
    python tools/scrape_dailyremote.py
    python tools/scrape_dailyremote.py --search "social media" --location "United States" --output job_listings.xlsx
"""

import argparse
import time
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import pandas as pd


BASE_URL = "https://dailyremote.com"
DEFAULT_SEARCH = "social media"
DEFAULT_LOCATION = "United States"
DEFAULT_OUTPUT = "job_listings.xlsx"
REQUEST_DELAY = 1.5  # seconds between requests to avoid rate limiting

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def build_url(search: str, location: str, page: int) -> str:
    from urllib.parse import urlencode
    params = {
        "search": search,
        "location_country": location,
        "page": page,
    }
    return f"{BASE_URL}/?{urlencode(params)}"


def parse_job_cards(soup: BeautifulSoup) -> list[dict]:
    """Parse all job cards from a page's BeautifulSoup object."""
    jobs = []
    # Job cards are <article class="card js-card">
    cards = soup.find_all("article", class_="card")
    for card in cards:
        job = extract_job_data(card)
        if job and job.get("title"):
            jobs.append(job)
    return jobs


def extract_job_data(card) -> dict:
    """Extract structured data from a single job card <article> element."""
    job = {
        "title": "",
        "company": "N/A (Premium)",
        "location": "",
        "date_posted": "",
        "job_url": "",
    }

    # --- Job URL ---
    # The job link is the <a> inside <h2 class="job-position">
    title_h2 = card.find("h2", class_="job-position")
    if title_h2:
        link = title_h2.find("a", href=True)
        if link:
            href = link.get("href", "")
            job["job_url"] = href if href.startswith("http") else BASE_URL + href
            job["title"] = link.get_text(strip=True)

    # --- Company ---
    # Company names are behind a paywall; the div.company-name instead shows
    # employment type and date. We attempt to read it anyway in case it's exposed.
    company_div = card.find("div", class_="company-name")
    if company_div:
        # The div contains: [employment-type] · [date-posted]
        # Real company name would be a separate element if unlocked
        spans = company_div.find_all("span", recursive=False)
        # If there are more than 3 spans, the extra ones may be the company name
        # (paywall unlocked). Otherwise, skip it — it's just "Full Time · X ago".
        if len(spans) > 3:
            job["company"] = spans[0].get_text(strip=True)

        # --- Date Posted ---
        # Third visible span: "8 hours ago", "2 days ago", etc.
        date_spans = [s for s in spans if s.get_text(strip=True) not in ("·", "")]
        if len(date_spans) >= 2:
            job["date_posted"] = date_spans[-1].get_text(strip=True)

    # --- Location ---
    # <span class="card-tag"> containing the globe emoji + country text
    job_meta = card.find("div", class_="job-meta")
    if job_meta:
        for tag_span in job_meta.find_all("span", class_="card-tag"):
            text = tag_span.get_text(strip=True)
            if "\U0001f30e" in text or "\U0001f30d" in text or "\U0001f30f" in text:
                # Strip globe emoji variants
                location_text = (
                    text.replace("\U0001f30e", "")
                        .replace("\U0001f30d", "")
                        .replace("\U0001f30f", "")
                        .strip()
                )
                job["location"] = location_text
                break

    return job


def scrape_page(search: str, location: str, page: int, session: requests.Session) -> list[dict]:
    url = build_url(search, location, page)
    print(f"  Fetching page {page}: {url}")

    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching page {page}: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    jobs = parse_job_cards(soup)
    print(f"  Found {len(jobs)} jobs on page {page}")
    return jobs


def scrape_all(search: str, location: str, max_pages: int = 50) -> list[dict]:
    all_jobs = []
    session = requests.Session()

    for page in range(1, max_pages + 1):
        jobs = scrape_page(search, location, page, session)
        if not jobs:
            print(f"  No jobs found on page {page} — stopping pagination.")
            break
        all_jobs.extend(jobs)
        if page < max_pages:
            time.sleep(REQUEST_DELAY)

    # Deduplicate by URL
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = job.get("job_url", "")
        if key and key not in seen:
            seen.add(key)
            unique_jobs.append(job)
        elif not key:
            unique_jobs.append(job)

    return unique_jobs


def save_to_excel(jobs: list[dict], output_path: str) -> None:
    df = pd.DataFrame(jobs, columns=["title", "company", "location", "date_posted", "job_url"])
    df.columns = ["Title", "Company", "Location", "Date Posted", "Job URL"]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Job Listings")

        # Auto-size columns
        ws = writer.sheets["Job Listings"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 80)

    print(f"\nSaved {len(jobs)} jobs to: {output.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Scrape DailyRemote job listings to Excel")
    parser.add_argument("--search", default=DEFAULT_SEARCH, help="Search term")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Location filter")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output Excel filename")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to scrape")
    args = parser.parse_args()

    print(f"Scraping DailyRemote: search='{args.search}', location='{args.location}'")
    print(f"Output: {args.output}\n")

    jobs = scrape_all(args.search, args.location, args.max_pages)

    if not jobs:
        print("No jobs found. Check the search term and location, or inspect the HTML structure.")
        sys.exit(1)

    print(f"\nTotal unique jobs scraped: {len(jobs)}")
    save_to_excel(jobs, args.output)


if __name__ == "__main__":
    main()
