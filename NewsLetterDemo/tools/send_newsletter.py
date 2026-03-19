"""
send_newsletter.py — Send a newsletter HTML file via Resend

CLI: python send_newsletter.py \
       --html .tmp/newsletters/<file>.html \
       --to recipient@example.com \
       --subject "Your Newsletter Subject" \
       --from "Newsletter <newsletter@yourdomain.com>" \
       --receipt .tmp/receipts/<file>.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def send_via_resend(html_content: str, to: str, subject: str, from_addr: str) -> dict:
    """Send an email via the Resend API. Returns the API response dict."""
    try:
        import resend
    except ImportError:
        print("ERROR: resend package not installed. Run: pip install resend", file=sys.stderr)
        sys.exit(1)

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("ERROR: RESEND_API_KEY not found in environment / .env file", file=sys.stderr)
        sys.exit(1)

    resend.api_key = api_key

    response = resend.Emails.send({
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": html_content,
    })
    return response


def save_receipt(receipt_data: dict, path: str) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(receipt_data, f, indent=2)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Send a newsletter via Resend.")
    parser.add_argument("--html", required=True, help="Path to the HTML newsletter file")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--from", dest="from_addr", default="Newsletter <newsletter@resend.dev>",
                        help="Sender address (default: newsletter@resend.dev)")
    parser.add_argument("--receipt", help="Optional path to save delivery receipt JSON")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"ERROR: HTML file not found: {html_path}", file=sys.stderr)
        sys.exit(1)

    html_content = html_path.read_text(encoding="utf-8")

    print(f"Sending newsletter to {args.to!r}...")
    response = send_via_resend(html_content, args.to, args.subject, args.from_addr)

    receipt = {
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "to": args.to,
        "subject": args.subject,
        "from": args.from_addr,
        "html_file": str(html_path),
        "resend_response": response,
    }

    if args.receipt:
        path = save_receipt(receipt, args.receipt)
        print(f"Receipt saved to: {path}")

    print(f"Email sent successfully. ID: {response.get('id', 'unknown')}")


if __name__ == "__main__":
    main()
