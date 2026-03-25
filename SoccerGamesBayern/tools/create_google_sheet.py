"""
create_google_sheet.py
Creates (or overwrites) a Google Sheet with the scraped BFV match data.

Usage:
    python tools/create_google_sheet.py --input .tmp/matches_YYYY-MM-DD.json
    python tools/create_google_sheet.py --input .tmp/matches_YYYY-MM-DD.json --title "BFV Matches March 2026"

Reads:
    .env              (GMAIL_SENDER — used as the Google account)
    credentials.json  (Google OAuth client secret)
    token.json        (saved OAuth token — created/updated on first run)

OAuth scopes required:
    https://www.googleapis.com/auth/spreadsheets
    https://www.googleapis.com/auth/drive.file

Output (stdout): JSON with sheet URL and sheet ID
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")


def get_credentials():
    """Load or refresh OAuth2 credentials. Runs browser flow on first use."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "ERROR: Google client libraries not installed.\n"
            "Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: credentials.json not found at {CREDENTIALS_FILE}", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def create_sheet(matches: list[dict], title: str) -> dict:
    """Create a Google Sheet with match data and return sheet URL + ID."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("ERROR: google-api-python-client not installed.", file=sys.stderr)
        sys.exit(1)

    creds = get_credentials()
    sheets_service = build("sheets", "v4", credentials=creds)

    # Create a new spreadsheet
    spreadsheet_body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "Upcoming Matches"}}],
    }
    spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet_body).execute()
    spreadsheet_id = spreadsheet["spreadsheetId"]
    sheet_grid_id = spreadsheet["sheets"][0]["properties"]["sheetId"]
    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    print(f"  Created sheet: {sheet_url}", file=sys.stderr)

    # Build rows: header + data
    headers = ["Date", "Time", "Home Team", "Visitor Team", "Location", "League"]
    rows = [headers]

    for m in matches:
        rows.append([
            m.get("date", ""),
            m.get("time", ""),
            m.get("home_team", ""),
            m.get("visitor_team", ""),
            m.get("location", ""),
            m.get("league", ""),
        ])

    # Write data to sheet
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Upcoming Matches!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # Format header row: bold + background color
    format_requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_grid_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.18, "green": 0.31, "blue": 0.57},
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "bold": True,
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        # Auto-resize all columns
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_grid_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 6,
                }
            }
        },
        # Freeze header row
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_grid_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": format_requests},
    ).execute()

    print(f"  Wrote {len(matches)} matches to sheet.", file=sys.stderr)
    return {"sheet_url": sheet_url, "sheet_id": spreadsheet_id, "row_count": len(matches)}


def main():
    parser = argparse.ArgumentParser(description="Create Google Sheet from BFV match data")
    parser.add_argument("--input", required=True, help="Path to matches JSON file")
    parser.add_argument("--title", help="Spreadsheet title (overrides default)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    matches = json.loads(input_path.read_text(encoding="utf-8"))
    if not matches:
        print("WARNING: No matches found in input file. Sheet will be empty.", file=sys.stderr)

    today = date.today().isoformat()
    title = args.title or f"BFV Upcoming Matches — {today}"

    print(f"Creating Google Sheet '{title}'...", file=sys.stderr)
    result = create_sheet(matches, title)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
