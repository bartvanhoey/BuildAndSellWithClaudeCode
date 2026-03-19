"""
preview_newsletter.py — Open a newsletter HTML file in the system browser

CLI: python preview_newsletter.py --html .tmp/newsletters/<file>.html
     python preview_newsletter.py  (opens most recent newsletter automatically)
"""

import argparse
import sys
import webbrowser
from pathlib import Path


def find_latest_newsletter() -> Path | None:
    """Return the most recently modified .html file in .tmp/newsletters/."""
    newsletters_dir = Path(".tmp/newsletters")
    if not newsletters_dir.exists():
        return None
    html_files = list(newsletters_dir.glob("*.html"))
    if not html_files:
        return None
    return max(html_files, key=lambda p: p.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(description="Open a newsletter HTML file in the browser.")
    parser.add_argument("--html", help="Path to the HTML file (omit to open the latest)")
    args = parser.parse_args()

    if args.html:
        html_path = Path(args.html)
    else:
        html_path = find_latest_newsletter()
        if html_path is None:
            print("ERROR: No HTML files found in .tmp/newsletters/. Run the newsletter workflow first.", file=sys.stderr)
            sys.exit(1)
        print(f"Opening latest newsletter: {html_path}")

    if not html_path.exists():
        print(f"ERROR: File not found: {html_path}", file=sys.stderr)
        sys.exit(1)

    url = "file:///" + str(html_path.resolve()).replace("\\", "/")
    print(f"Opening: {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    main()
