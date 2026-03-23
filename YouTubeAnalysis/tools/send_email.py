"""
send_email.py
Sends the .pptx deck as a Gmail attachment via the Gmail API.

Usage:
    python tools/send_email.py --attachment .tmp/decks/youtube_trends_2026-03-23.pptx
    python tools/send_email.py --attachment <path> --to override@example.com

Reads:
    .env              (GMAIL_SENDER)
    config.json       (email_recipient, email_subject_template, sender_name)
    credentials.json  (Google OAuth client secret)
    token.json        (saved OAuth token — created on first run)

OAuth scope: https://www.googleapis.com/auth/gmail.send (send-only, minimal permissions)

First run opens a browser for OAuth consent and saves token.json.
Subsequent runs use the saved token automatically.

Output (stdout): JSON receipt
Writes: .tmp/receipts/email_receipt_YYYY-MM-DD.json
"""

import argparse
import base64
import json
import os
import sys
from datetime import date, datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
RECEIPTS_DIR = TMP_DIR / "receipts"
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    print(
        "ERROR: Google client libraries not installed.\n"
        "Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2",
        file=sys.stderr,
    )
    sys.exit(1)


def get_credentials() -> Credentials:
    """Load or refresh OAuth2 credentials. Runs browser flow on first use."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(
                    "ERROR: credentials.json not found.\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials\n"
                    "Enable the Gmail API and create an OAuth 2.0 Client ID (Desktop app).\n"
                    f"Place the file at: {CREDENTIALS_FILE}",
                    file=sys.stderr,
                )
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


def build_email(sender: str, recipient: str, subject: str,
                body: str, attachment_path: Path) -> str:
    """Build a base64url-encoded email with a .pptx attachment."""
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with open(attachment_path, "rb") as f:
        attachment = MIMEApplication(
            f.read(),
            _subtype="vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    attachment.add_header(
        "Content-Disposition", "attachment", filename=attachment_path.name
    )
    msg.attach(attachment)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return raw


def main():
    parser = argparse.ArgumentParser(description="Send YouTube trends deck via Gmail")
    parser.add_argument("--attachment", required=True, help="Path to the .pptx file to send")
    parser.add_argument("--to", help="Override recipient email address")
    parser.add_argument("--subject", help="Override email subject")
    args = parser.parse_args()

    attachment_path = Path(args.attachment)
    if not attachment_path.exists():
        print(f"ERROR: Attachment not found: {attachment_path}", file=sys.stderr)
        sys.exit(1)

    if attachment_path.stat().st_size == 0:
        print("ERROR: Attachment file is empty — deck generation may have failed.", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    sender_email = os.getenv("GMAIL_SENDER")
    if not sender_email:
        print("ERROR: GMAIL_SENDER is not set in .env", file=sys.stderr)
        sys.exit(1)

    recipient = args.to or config.get("email_recipient", "")
    if not recipient:
        print(
            "ERROR: No recipient specified. Set email_recipient in config.json or use --to",
            file=sys.stderr,
        )
        sys.exit(1)

    today = date.today().isoformat()
    subject_template = config.get("email_subject_template", "YouTube AI Trends — Week of {date}")
    subject = args.subject or subject_template.format(date=today)

    sender_name = config.get("sender_name", "YouTube Trends Bot")
    body = (
        f"Hi,\n\n"
        f"Attached is your weekly YouTube AI & Automation trend report for the week of {today}.\n\n"
        f"This report covers:\n"
        f"  • Top trending videos by view count\n"
        f"  • View velocity rankings (what's growing fastest right now)\n"
        f"  • Engagement rate analysis\n"
        f"  • Top keywords found in titles\n"
        f"  • Top channels to watch\n"
        f"  • Transcript theme analysis\n"
        f"  • Content opportunity gaps and recommended video ideas\n\n"
        f"— {sender_name}\n"
    )

    print("  Authenticating with Gmail...", file=sys.stderr)
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    print(f"  Sending to {recipient}...", file=sys.stderr)
    raw_message = build_email(
        sender=sender_email,
        recipient=recipient,
        subject=subject,
        body=body,
        attachment_path=attachment_path,
    )

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
        "attachment": str(attachment_path),
    }

    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPTS_DIR / f"email_receipt_{today}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
