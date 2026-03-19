"""
parse_brand_assets.py
Reads brand_assets/colors.txt and confirms Logo.png exists.
Writes .tmp/brand_config.json with resolved hex values.

Usage:
    python tools/parse_brand_assets.py
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
COLORS_FILE = PROJECT_ROOT / "brand_assets" / "colors.txt"
LOGO_FILE = PROJECT_ROOT / "brand_assets" / "Logo.png"
TMP_DIR = PROJECT_ROOT / ".tmp"
OUTPUT_FILE = TMP_DIR / "brand_config.json"

# CSS variable names to extract
TARGET_VARS = {
    "primary_color": "--color-primary-400",
    "secondary_color": "--color-secondary-400",
}


def parse_colors(colors_text: str) -> dict[str, str]:
    """Extract hex values for target CSS variables."""
    result = {}
    for key, var_name in TARGET_VARS.items():
        # Match:  --color-primary-400: #093824;  (with optional comment)
        pattern = rf"{re.escape(var_name)}:\s*(#[0-9a-fA-F]{{3,8}})"
        match = re.search(pattern, colors_text)
        if match:
            result[key] = match.group(1).lower()
        else:
            print(f"WARNING: Could not find {var_name} in colors.txt", file=sys.stderr)
            result[key] = None
    return result


def main():
    TMP_DIR.mkdir(exist_ok=True)

    if not COLORS_FILE.exists():
        print(f"ERROR: {COLORS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    colors_text = COLORS_FILE.read_text(encoding="utf-8")
    colors = parse_colors(colors_text)

    logo_exists = LOGO_FILE.exists()
    if not logo_exists:
        print(f"WARNING: {LOGO_FILE} not found — PDF cover will use text-only header", file=sys.stderr)

    config = {
        "primary_color": colors.get("primary_color", "#093824"),
        "secondary_color": colors.get("secondary_color", "#c0652a"),
        "logo_path": str(LOGO_FILE) if logo_exists else None,
    }

    OUTPUT_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps(config, indent=2))
    return config


if __name__ == "__main__":
    main()
