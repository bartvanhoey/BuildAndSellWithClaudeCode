"""
send_email.py
Sends a Gmail notification with the Google Sheet link for BFV upcoming matches.

Usage:
    python tools/send_email.py --sheet-url "https://docs.google.com/..." --row-count 42
    python tools/send_email.py --sheet-url "..." --row-count 42 --to override@example.com

Reads:
    .env              (GMAIL_SENDER)
    config.json       (email_recipient, email_subject_template, sender_name)
    credentials.json  (Google OAuth client secret)
    token.json        (saved OAuth token)

OAuth scope: https://www.googleapis.com/auth/gmail.send

Output (stdout): JSON receipt
Writes: .tmp/receipts/email_receipt_YYYY-MM-DD.json
"""

import argparse
import base64
import json
import os
import sys
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
RECEIPTS_DIR = TMP_DIR / "receipts"
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")


def get_credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: Google client libraries not installed.", file=sys.stderr)
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


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def build_email(sender: str, recipient: str, subject: str, body: str) -> str:
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Send BFV matches sheet link via Gmail")
    parser.add_argument("--sheet-url", required=True, help="Google Sheet URL")
    parser.add_argument("--row-count", type=int, default=0, help="Number of matches found")
    parser.add_argument("--to", help="Override recipient email address")
    parser.add_argument("--subject", help="Override email subject")
    args = parser.parse_args()

    config = load_config()
    sender_email = os.getenv("GMAIL_SENDER")
    if not sender_email:
        print("ERROR: GMAIL_SENDER is not set in .env", file=sys.stderr)
        sys.exit(1)

    recipient = args.to or config.get("email_recipient", "")
    if not recipient:
        print("ERROR: No recipient specified.", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    subject_template = config.get("email_subject_template", "BFV Upcoming Matches — {date}")
    subject = args.subject or subject_template.format(date=today)
    sender_name = config.get("sender_name", "BFV Match Bot")
    leagues = config.get("leagues", ["Kreisliga", "Bezirksliga"])
    leagues_str = " & ".join(leagues)

    body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
  <div style="background-color: #1B3A6B; padding: 20px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">BFV Upcoming Matches</h1>
    <p style="color: #ccd9f0; margin: 4px 0 0 0;">{leagues_str} — Next 2 Weeks</p>
  </div>
  <div style="border: 1px solid #ddd; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
    <p>Hi,</p>
    <p>Your BFV match overview for the next 14 days is ready.</p>
    <p><strong>{args.row_count} upcoming matches</strong> found across {leagues_str}.</p>
    <p style="margin: 24px 0;">
      <a href="{args.sheet_url}"
         style="background-color: #1B3A6B; color: white; padding: 12px 24px;
                text-decoration: none; border-radius: 6px; font-weight: bold;">
        Open Google Sheet →
      </a>
    </p>
    <p style="color: #888; font-size: 13px;">Data scraped from bfv.de on {today}</p>
    <p style="color: #888; font-size: 13px;">— {sender_name}</p>
  </div>
</body>
</html>
"""

    print("  Authenticating with Gmail...", file=sys.stderr)
    creds = get_credentials()

    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("ERROR: google-api-python-client not installed.", file=sys.stderr)
        sys.exit(1)

    service = build("gmail", "v1", credentials=creds)

    print(f"  Sending to {recipient}...", file=sys.stderr)
    raw_message = build_email(sender_email, recipient, subject, body)

    try:
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw_message},
        ).execute()
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)

    sent_at = datetime.now(timezone.utc).isoformat()
    receipt = {
        "status": "sent",
        "message_id": result.get("id"),
        "sent_at": sent_at,
        "to": recipient,
        "subject": subject,
        "sheet_url": args.sheet_url,
    }

    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPTS_DIR / f"email_receipt_{today}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
