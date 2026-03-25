"""
scrape_bfv_matches.py
Scrapes upcoming matches from bfv.de for Kreisliga and Bezirksliga leagues
using direct HTTP requests + font-based obfuscation decoding.

How it works:
  1. Calls the internal BFV API to get all competition IDs for selected leagues
  2. For each competition, iterates through spieltag pages
  3. Each page uses a unique custom font (anti-scraping obfuscation)
  4. Downloads the font, builds a unicode->char decode map, decodes the HTML
  5. Extracts match data (date, time, home team, visitor team) from decoded HTML

Usage:
    python tools/scrape_bfv_matches.py
    python tools/scrape_bfv_matches.py --days 14 --leagues "Kreisliga,Bezirksliga"

Reads:
    config.json  (leagues, lookahead_days)

Output (stdout): JSON list of match objects
Writes: .tmp/matches_YYYY-MM-DD.json

Note: No API keys or authentication required. BFV website is publicly accessible.
"""

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")

# ── Font decode map ──────────────────────────────────────────────────────────

GLYPH_TO_CHAR: dict[str, str] = {}
for _d, _n in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]):
    GLYPH_TO_CHAR[_n] = str(_d)
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
    GLYPH_TO_CHAR[_c] = _c
GLYPH_TO_CHAR.update({
    "period": ".", "colon": ":", "space": " ", "hyphen": "-", "slash": "/",
    "comma": ",", "exclam": "!", "question": "?", "ampersand": "&",
    "parenleft": "(", "parenright": ")", "underscore": "_",
    "semicolon": ";",
    # German umlauts
    "Adieresis": "Ä", "adieresis": "ä",
    "Odieresis": "Ö", "odieresis": "ö",
    "Udieresis": "Ü", "udieresis": "ü",
    "germandbls": "ß",
    # Accented
    "Aacute": "Á", "aacute": "á", "Eacute": "É", "eacute": "é",
    "Iacute": "Í", "iacute": "í", "Oacute": "Ó", "oacute": "ó",
    "Uacute": "Ú", "uacute": "ú",
    "Ccedilla": "Ç", "ccedilla": "ç",
    "Ntilde": "Ñ", "ntilde": "ñ",
    "Nacute": "Ń", "nacute": "ń",
    "Zcaron": "Ž", "zcaron": "ž", "Scaron": "Š", "scaron": "š",
    "Acircumflex": "Â", "acircumflex": "â",
    "Ecircumflex": "Ê", "ecircumflex": "ê",
    "Icircumflex": "Î", "icircumflex": "î",
    "Ocircumflex": "Ô", "ocircumflex": "ô",
    "Ucircumflex": "Û", "ucircumflex": "û",
    "agrave": "à", "egrave": "è", "igrave": "ì", "ograve": "ò", "ugrave": "ù",
})


def build_decode_map(font_bytes: bytes) -> dict[int, str]:
    """Build a unicode codepoint → visible character map from a BFV font file."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print(
            "ERROR: fonttools not installed.\n"
            "Run: pip install fonttools",
            file=sys.stderr,
        )
        sys.exit(1)
    font = TTFont(BytesIO(font_bytes))
    cmap = font.getBestCmap()
    return {cp: GLYPH_TO_CHAR[gn] for cp, gn in cmap.items() if gn in GLYPH_TO_CHAR}


def decode_html(html_text: str, decode_map: dict[int, str]) -> str:
    """Decode BFV-obfuscated HTML: private-use unicode chars → visible chars."""
    return "".join(
        decode_map.get(ord(c), "") if ord(c) >= 0xE000 else c
        for c in html_text
    )


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def make_opener() -> urllib.request.OpenerDirector:
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"),
        ("Accept", "text/html,application/xhtml+xml,*/*;q=0.9"),
        ("Accept-Language", "de-DE,de;q=0.9,en;q=0.8"),
        ("Referer", "https://www.bfv.de/"),
    ]
    return opener


def fetch_page(url: str, opener: urllib.request.OpenerDirector, timeout: int = 15) -> str:
    """Fetch a page and return decoded HTML with font-based text decoding applied."""
    with opener.open(url, timeout=timeout) as r:
        raw_html = r.read().decode("utf-8", errors="replace")

    # Find the unique font ID embedded in this page's HTML
    font_ids = re.findall(r"fontface/-/format/ttf/id/([^/]+)/type/font", raw_html)
    if not font_ids:
        return raw_html  # No obfuscation on this page

    font_id = font_ids[0]
    ttf_url = f"https://app.bfv.de/export.fontface/-/format/ttf/id/{font_id}/type/font"

    with opener.open(ttf_url, timeout=timeout) as r:
        font_bytes = r.read()

    decode_map = build_decode_map(font_bytes)
    return decode_html(raw_html, decode_map)


# ── BFV API helpers ──────────────────────────────────────────────────────────

def get_competition_ids(
    league_slug: str,
    league_id: str,
    opener: urllib.request.OpenerDirector,
) -> list[dict]:
    """
    Query the BFV WAM3 API to get all sub-competition IDs for a league.
    Returns list of dicts: {id, name}
    """
    # Map friendly league names to BFV spielklasse IDs
    LEAGUE_IDS = {
        "Kreisliga": "392",
        "Bezirksliga": "390",
        "Kreisklasse": "393",
        "A Klasse": "394",
        "B Klasse": "395",
    }
    spielklasse_id = LEAGUE_IDS.get(league_slug)
    if not spielklasse_id:
        print(f"  WARNING: Unknown league '{league_slug}'. Skipping.", file=sys.stderr)
        return []

    api_url = (
        f"https://next.bfv.de/bfv-api/v1/public/getBfvWamThree"
        f"/wettkampftyp/1/saison/2526/spielklasse/{spielklasse_id}/mannschaftsart/359"
    )

    req = urllib.request.Request(api_url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.bfv.de/",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ERROR fetching competition list for {league_slug}: {e}", file=sys.stderr)
        return []

    competitions = []
    for kreis_id, comps in data.get("competitions", {}).get(spielklasse_id, {}).items():
        for comp in comps:
            competitions.append({"id": comp["id"], "name": comp["value"], "league": league_slug})

    return competitions


# ── Match parser ─────────────────────────────────────────────────────────────

def parse_matches(decoded_html: str, competition_name: str, league: str,
                  today: date, cutoff: date) -> list[dict]:
    """Extract match rows from decoded BFV competition page HTML."""
    start = decoded_html.find("Datum / Zeit")
    section = decoded_html[start:start + 30000] if start != -1 else ""
    visible = re.sub(r"<[^>]+>", " ", section)
    visible = re.sub(r"\s+", " ", visible).strip()

    matches = []
    # Split on weekday markers that start a match entry
    entries = re.split(r"(?=(?:Mo|Di|Mi|Do|Fr|Sa|So)\.,\s+\d{2}\.\d{2}\.\d{4})", visible)

    for entry in entries:
        date_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", entry)
        time_m = re.search(r"(\d{2}:\d{2})\s*Uhr", entry)
        if not date_m:
            continue

        match_date_str = date_m.group(1)
        try:
            match_date = datetime.strptime(match_date_str, "%d.%m.%Y").date()
        except ValueError:
            continue

        if match_date < today or match_date > cutoff:
            continue

        match_time = time_m.group(1) if time_m else ""

        # Text after the time
        after_time_start = time_m.end() if time_m else date_m.end()
        after_time = entry[after_time_start:]
        after_time = re.sub(r"Uhr\s*", "", after_time)
        after_time = re.sub(r"\s+", " ", after_time).strip()

        # Remove "ZUM SPIEL" and everything after
        after_time = re.split(r"ZUM SPIEL", after_time)[0].strip()

        # Future matches show "- : -" separator between teams
        future_sep = re.search(r"\s*-\s*:\s*-\s*", after_time)
        score_m = re.search(r"(\d+:\d+)", after_time)
        ticker_m = re.search(r"\bTicker\b", after_time)

        if future_sep:
            home = after_time[:future_sep.start()].strip()
            away = after_time[future_sep.end():].strip()
        elif score_m:
            home = after_time[:score_m.start()].strip()
            away = after_time[score_m.end():].strip()
            away = re.sub(r"\(\d+:\d+\)", "", away).strip()
        elif ticker_m:
            home = after_time[:ticker_m.start()].strip()
            away = after_time[ticker_m.end():].strip()
        else:
            home = after_time
            away = ""

        # Clean up team names
        home = re.sub(r"\s+", " ", home).strip(" -")
        away = re.sub(r"\s+", " ", away).strip(" -")

        if not home:
            continue

        matches.append({
            "league": league,
            "competition": competition_name,
            "date": match_date_str,
            "time": match_time,
            "home_team": home,
            "visitor_team": away,
            "location": "",
        })

    return matches


# ── Main ─────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def scrape_league(league: str, lookahead_days: int,
                  opener: urllib.request.OpenerDirector) -> list[dict]:
    """Scrape all upcoming matches for a given league within the next N days."""
    today = date.today()
    cutoff = today + timedelta(days=lookahead_days)

    print(f"  Fetching competition list for {league}...", file=sys.stderr)
    competitions = get_competition_ids(league, league, opener)
    print(f"    Found {len(competitions)} competitions", file=sys.stderr)

    all_matches = []

    for comp in competitions:
        comp_id = comp["id"]
        comp_name = comp["name"]
        print(f"    Scraping {comp_name} ({comp_id})...", file=sys.stderr)

        # Try spieltag pages: check current and next ~5 spieltage
        # First load default page to find current spieltag
        base_url = f"https://www.bfv.de/ergebnisse/wettbewerb/-/{comp_id}"

        try:
            decoded = fetch_page(base_url, opener)
            # Find current spieltag number
            spieltag_m = re.search(r"(\d+)\.\s*Spieltag", decoded)
            current_spieltag = int(spieltag_m.group(1)) if spieltag_m else 1
        except Exception as e:
            print(f"      ERROR loading {comp_name}: {e}", file=sys.stderr)
            continue

        # Check current spieltag and next 3
        spieltage_to_check = list(range(current_spieltag, current_spieltag + 4))
        found_any = False

        for st in spieltage_to_check:
            try:
                url = f"{base_url}/spieltag/{st}"
                decoded = fetch_page(url, opener)
                matches = parse_matches(decoded, comp_name, league, today, cutoff)
                if matches:
                    all_matches.extend(matches)
                    found_any = True
                    print(f"      Spieltag {st}: {len(matches)} upcoming matches", file=sys.stderr)
                else:
                    # Check if all matches on this spieltag are in the past
                    dates = re.findall(r"\d{2}\.\d{2}\.\d{4}", decoded[decoded.find("Datum"):decoded.find("Datum")+5000] if "Datum" in decoded else "")
                    if dates:
                        last_date = max(datetime.strptime(d, "%d.%m.%Y").date() for d in dates)
                        if last_date < today:
                            continue  # All in past, check next
                        elif last_date > cutoff:
                            break  # All in future beyond window
                time.sleep(0.5)  # Be polite
            except Exception as e:
                print(f"      ERROR spieltag {st}: {e}", file=sys.stderr)
                break

        time.sleep(1)  # Pause between competitions

    return all_matches


def main():
    parser = argparse.ArgumentParser(description="Scrape upcoming BFV matches")
    parser.add_argument("--days", type=int, help="Lookahead days (overrides config)")
    parser.add_argument("--leagues", help="Comma-separated league names (overrides config)")
    args = parser.parse_args()

    config = load_config()
    lookahead_days = args.days or config.get("lookahead_days", 14)
    leagues = (
        [l.strip() for l in args.leagues.split(",")]
        if args.leagues
        else config.get("leagues", ["Kreisliga", "Bezirksliga"])
    )

    print(f"Scraping BFV for {leagues} — next {lookahead_days} days...", file=sys.stderr)

    opener = make_opener()
    all_matches = []

    for league in leagues:
        print(f"\nLeague: {league}", file=sys.stderr)
        matches = scrape_league(league, lookahead_days, opener)
        all_matches.extend(matches)
        print(f"  Total: {len(matches)} matches", file=sys.stderr)

    today_str = date.today().isoformat()
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TMP_DIR / f"matches_{today_str}.json"
    output_path.write_text(
        json.dumps(all_matches, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nSaved {len(all_matches)} total matches to {output_path}", file=sys.stderr)
    output = json.dumps(all_matches, indent=2, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
