"""
upload_to_drive.py
Uploads a PDF to Google Drive and returns a shareable link.

Usage:
    python tools/upload_to_drive.py --file .tmp/competitor_report_2026-03-19.pdf
    python tools/upload_to_drive.py --file .tmp/competitor_report_2026-03-19.pdf --folder-id 1AbCdEf...

Requires:
    credentials.json    (Google OAuth client secret, download from Google Cloud Console)
    google-api-python-client, google-auth-oauthlib, google-auth-httplib2

First run:
    Opens a browser for OAuth consent. Saves token.json for subsequent runs.

Output (stdout): JSON with keys: file_id, shareable_link, web_view_link
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
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
                    f"Place it at: {CREDENTIALS_FILE}",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_to_drive(file_path: Path, folder_id: str | None = None) -> dict:
    """
    Upload a file to Google Drive.

    Args:
        file_path:  Local path to the file
        folder_id:  Google Drive folder ID (optional)

    Returns:
        dict with file_id, shareable_link, web_view_link
    """
    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    file_metadata = {"name": file_path.name}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(str(file_path), mimetype="application/pdf", resumable=True)

    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id,webViewLink,webContentLink")
        .execute()
    )

    file_id = uploaded.get("id")

    # Make it viewable by anyone with the link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    # Re-fetch to get the updated webViewLink
    file_info = service.files().get(fileId=file_id, fields="id,webViewLink,name").execute()

    return {
        "file_id": file_id,
        "name": file_info.get("name"),
        "shareable_link": file_info.get("webViewLink"),
        "web_view_link": file_info.get("webViewLink"),
    }


def main():
    parser = argparse.ArgumentParser(description="Upload a PDF to Google Drive")
    parser.add_argument("--file", required=True, help="Path to the PDF file")
    parser.add_argument("--folder-id", help="Google Drive folder ID (optional)")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = upload_to_drive(file_path, args.folder_id)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(
            json.dumps({
                "error": str(e),
                "message": "Upload failed. PDF is available locally.",
                "local_path": str(file_path),
            }, indent=2)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
