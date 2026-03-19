"""
generate_html.py — Assemble a styled HTML newsletter from content JSON + optional SVG infographics

CLI: python generate_html.py --content .tmp/content_<slug>.json --template default --output .tmp/newsletters/<date>_<slug>.html

Content JSON shape:
{
  "subject":   "...",
  "headline":  "...",
  "intro":     "...",
  "sections":  [{ "title": "...", "body": "...", "infographic": "<path-or-null>" }],
  "conclusion": "...",
  "cta":       { "text": "...", "url": "..." },
  "social_variants": { "twitter": "...", "linkedin": "..." },
  "sources":   [{ "title": "...", "url": "..." }]
}
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── CSS loading ──────────────────────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_template(name: str) -> str:
    """Return CSS for the named template (default / dark / minimal)."""
    path = TEMPLATES_DIR / f"{name}.css"
    if not path.exists():
        available = [p.stem for p in TEMPLATES_DIR.glob("*.css")]
        raise FileNotFoundError(
            f"Template '{name}' not found. Available: {', '.join(available)}"
        )
    return path.read_text(encoding="utf-8")


def resolve_css_vars(css: str) -> str:
    """
    Resolve CSS custom properties to literal values for email-client compatibility.
    Email clients (Outlook, Hotmail) do not support var(--x).
    Steps:
      1. Strip @import lines (Google Fonts — not supported in email)
      2. Parse :root { } block to build a var→value map
      3. Replace all var(--x) occurrences with their resolved values
      4. Remove the :root block itself (no longer needed)
    """
    # 1. Strip @import
    css = re.sub(r"@import\s+url\([^)]+\);?\s*\n?", "", css)

    # 2. Parse :root block
    root_match = re.search(r":root\s*\{([^}]+)\}", css, re.DOTALL)
    var_map = {}
    if root_match:
        for line in root_match.group(1).splitlines():
            m = re.match(r"\s*(--[\w-]+)\s*:\s*([^;/]+)", line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip().rstrip(",")
                var_map[key] = val

    # 3. Iteratively resolve var() — up to 3 passes for nested vars
    def replace_vars(text):
        def replacer(m):
            name = m.group(1).strip()
            fallback = m.group(2).strip() if m.group(2) else None
            return var_map.get(name, fallback or m.group(0))
        return re.sub(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\)", replacer, text)

    for _ in range(3):
        css = replace_vars(css)

    # 4. Remove :root block
    css = re.sub(r":root\s*\{[^}]+\}", "", css, flags=re.DOTALL)

    return css


# ── SVG embedding ─────────────────────────────────────────────────────────────

def embed_svg(svg_path: str) -> str:
    """Read an SVG file and return its content for inline embedding."""
    path = Path(svg_path)
    if not path.exists():
        return f'<!-- SVG not found: {svg_path} -->'
    content = path.read_text(encoding="utf-8").strip()
    # Strip XML declaration if present
    if content.startswith("<?xml"):
        content = content[content.index(">") + 1:].lstrip()
    return content


# ── HTML building ─────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _paragraphs(text: str) -> str:
    """Convert newline-separated paragraphs to <p> tags."""
    paras = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    return "\n".join(f"<p>{_esc(p)}</p>" for p in paras)


def build_html_structure(content: dict, css: str, generated_at: str) -> str:
    """Assemble the full HTML document."""
    headline = _esc(content.get("headline", "Newsletter"))
    subject = _esc(content.get("subject", headline))
    intro = _paragraphs(content.get("intro", ""))
    conclusion = _paragraphs(content.get("conclusion", ""))
    cta = content.get("cta", {})
    sources = content.get("sources", [])
    sections = content.get("sections", [])
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # ── Sections ──
    sections_html = ""
    for sec in sections:
        title = _esc(sec.get("title", ""))
        body = _paragraphs(sec.get("body", ""))
        infographic_path = sec.get("infographic")
        infographic_html = ""
        if infographic_path:
            svg_content = embed_svg(infographic_path)
            infographic_html = f'\n    <div class="infographic-wrap">\n      {svg_content}\n    </div>'
        sections_html += f"""
  <div class="email-section">
    <h2>{title}</h2>
    {body}{infographic_html}
  </div>"""

    # ── CTA ──
    cta_html = ""
    if cta.get("url") and cta.get("text"):
        cta_html = f"""
  <div class="cta-block">
    <a href="{_esc(cta['url'])}" class="cta-button">{_esc(cta['text'])}</a>
  </div>"""

    # ── Sources ──
    sources_html = ""
    if sources:
        items = ""
        for src in sources[:8]:
            title_text = _esc(src.get("title", src.get("url", "")))
            url = _esc(src.get("url", "#"))
            items += f'      <li><a href="{url}">{title_text}</a></li>\n'
        sources_html = f"""
  <div class="sources-block">
    <h3>Sources</h3>
    <ol>
{items}    </ol>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
{css}
  </style>
</head>
<body>
  <div class="email-wrapper">

    <div class="email-header">
      <span class="brand">Newsletter</span>
      <h1>{headline}</h1>
      <span class="issue-meta">{date_str}</span>
    </div>

    <div class="email-intro">
      {intro}
    </div>
{sections_html}

    <div class="email-conclusion">
      {conclusion}
    </div>
{cta_html}
{sources_html}

    <div class="email-footer">
      <p>Generated {generated_at} · WAT Newsletter Automation</p>
    </div>

  </div>
</body>
</html>"""


# ── CSS inlining ─────────────────────────────────────────────────────────────

def inline_css(html: str) -> str:
    """
    Resolve CSS variables then use premailer to inline styles.
    Always resolves vars first — email clients don't support var(--x).
    """
    # Resolve vars in the <style> block before premailer sees it
    def resolve_style_block(m):
        return "<style>\n" + resolve_css_vars(m.group(1)) + "\n</style>"

    html = re.sub(r"<style>(.*?)</style>", resolve_style_block, html, flags=re.DOTALL)

    try:
        import premailer
        return premailer.transform(html, remove_classes=False, strip_important=False)
    except ImportError:
        print("WARNING: premailer not installed — CSS not inlined. Run: pip install premailer", file=sys.stderr)
        return html


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_newsletter(content_path: str, template: str, output: str, inline: bool = True) -> Path:
    """Full pipeline: load content → load CSS → build HTML → inline CSS → save.
    inline=True by default — always inline for email compatibility.
    """
    with open(content_path, encoding="utf-8") as f:
        content = json.load(f)

    css = load_template(template)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = build_html_structure(content, css, generated_at)

    if inline:
        html = inline_css(html)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Assemble HTML newsletter from content JSON.")
    parser.add_argument("--content", required=True, help="Path to the content JSON file")
    parser.add_argument("--template", default="default", help="CSS template name (default/dark/minimal)")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    parser.add_argument("--no-inline-css", action="store_true", help="Skip CSS inlining (browser preview only)")
    args = parser.parse_args()

    out_path = generate_newsletter(args.content, args.template, args.output, inline=not args.no_inline_css)
    print(f"Newsletter saved to: {out_path}")


if __name__ == "__main__":
    main()
