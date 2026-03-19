"""
generate_infographic.py — Pure-Python SVG infographic renderer

CLI: python generate_infographic.py --spec .tmp/infographic_specs/stat_01.json --output .tmp/infographics/slug/stat_01.svg

Renderer types (set "type" in the spec JSON):
  stat_callout    — Large number + supporting label
  comparison      — Two-column side-by-side comparison
  timeline        — Horizontal timeline with labelled nodes
  process_steps   — Numbered vertical step flow
  quote_card      — Styled pull quote with attribution
"""

import argparse
import json
import sys
from pathlib import Path


# ── Shared helpers ──────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape special XML characters for SVG text content."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap text into lines of at most max_chars characters."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars or not current:
            current = (current + " " + word).strip()
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ── Renderer: stat_callout ──────────────────────────────────────────────────

def render_stat_callout(spec: dict) -> str:
    """
    spec keys:
      value        — e.g. "73%"
      label        — e.g. "of enterprises plan to increase AI spend in 2026"
      context      — (optional) small caption below
      accent       — hex color (default #093824 brand green)
    """
    value = _esc(spec.get("value", "?"))
    label = spec.get("label", "")
    context = spec.get("context", "")
    accent = spec.get("accent", "#093824")

    label_lines = _wrap_text(label, 38)
    label_y_start = 130
    label_svg = ""
    for i, line in enumerate(label_lines):
        label_svg += f'  <text x="280" y="{label_y_start + i * 26}" font-family="sans-serif" font-size="18" fill="#374151" text-anchor="middle">{_esc(line)}</text>\n'

    height = max(200, 140 + len(label_lines) * 26 + (40 if context else 0))
    context_svg = ""
    if context:
        context_svg = f'  <text x="280" y="{height - 20}" font-family="sans-serif" font-size="13" fill="#9ca3af" text-anchor="middle">{_esc(context)}</text>\n'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" width="560" height="{height}">
  <rect width="560" height="{height}" rx="8" fill="#eef7f3"/>
  <rect x="0" y="0" width="6" height="{height}" rx="3" fill="{accent}"/>
  <text x="280" y="100" font-family="sans-serif" font-size="72" font-weight="800" fill="{accent}" text-anchor="middle">{value}</text>
{label_svg}{context_svg}</svg>"""


# ── Renderer: comparison ────────────────────────────────────────────────────

def render_comparison(spec: dict) -> str:
    """
    spec keys:
      title        — chart title
      left         — { label, value, description }
      right        — { label, value, description }
      accent_left  — hex (default #2563eb)
      accent_right — hex (default #059669)
    """
    title = spec.get("title", "")
    left = spec.get("left", {})
    right = spec.get("right", {})
    al = spec.get("accent_left", "#093824")
    ar = spec.get("accent_right", "#c0652a")

    def col_svg(x_center, item, accent):
        label = _esc(item.get("label", ""))
        value = _esc(item.get("value", ""))
        desc_lines = _wrap_text(item.get("description", ""), 22)
        svg = f'  <text x="{x_center}" y="80" font-family="sans-serif" font-size="13" font-weight="700" fill="{accent}" text-anchor="middle" letter-spacing="1">{label}</text>\n'
        svg += f'  <text x="{x_center}" y="140" font-family="sans-serif" font-size="52" font-weight="800" fill="{accent}" text-anchor="middle">{value}</text>\n'
        for i, line in enumerate(desc_lines):
            svg += f'  <text x="{x_center}" y="{172 + i * 22}" font-family="sans-serif" font-size="14" fill="#374151" text-anchor="middle">{_esc(line)}</text>\n'
        return svg

    height = 260
    title_svg = f'  <text x="280" y="36" font-family="sans-serif" font-size="16" font-weight="700" fill="#111827" text-anchor="middle">{_esc(title)}</text>\n' if title else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" width="560" height="{height}">
  <rect width="560" height="{height}" rx="8" fill="#f9fafb"/>
  <rect x="280" y="50" width="1" height="{height - 80}" fill="#e5e7eb"/>
{title_svg}{col_svg(140, left, al)}{col_svg(420, right, ar)}</svg>"""


# ── Renderer: timeline ──────────────────────────────────────────────────────

def render_timeline(spec: dict) -> str:
    """
    spec keys:
      title   — chart title
      events  — list of { year, label }
      accent  — hex color
    """
    title = spec.get("title", "")
    events = spec.get("events", [])
    accent = spec.get("accent", "#093824")

    if not events:
        events = [{"year": "?", "label": "No events provided"}]

    n = len(events)
    width = 560
    height = 160
    pad = 60
    spacing = (width - 2 * pad) / max(n - 1, 1)

    nodes_svg = ""
    for i, ev in enumerate(events):
        x = pad + i * spacing
        year = _esc(str(ev.get("year", "")))
        label_lines = _wrap_text(ev.get("label", ""), 12)
        nodes_svg += f'  <circle cx="{x:.1f}" cy="80" r="10" fill="{accent}"/>\n'
        nodes_svg += f'  <text x="{x:.1f}" y="62" font-family="sans-serif" font-size="13" font-weight="700" fill="{accent}" text-anchor="middle">{year}</text>\n'
        for j, line in enumerate(label_lines):
            nodes_svg += f'  <text x="{x:.1f}" y="{100 + j * 18}" font-family="sans-serif" font-size="12" fill="#374151" text-anchor="middle">{_esc(line)}</text>\n'

    title_svg = f'  <text x="280" y="24" font-family="sans-serif" font-size="14" font-weight="700" fill="#111827" text-anchor="middle">{_esc(title)}</text>\n' if title else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" width="560" height="{height}">
  <rect width="560" height="{height}" rx="8" fill="#f9fafb"/>
  <line x1="{pad:.1f}" y1="80" x2="{width - pad:.1f}" y2="80" stroke="{accent}" stroke-width="2" opacity="0.3"/>
{title_svg}{nodes_svg}</svg>"""


# ── Renderer: process_steps ─────────────────────────────────────────────────

def render_process_steps(spec: dict) -> str:
    """
    spec keys:
      title  — chart title
      steps  — list of { title, description }
      accent — hex color
    """
    title = spec.get("title", "")
    steps = spec.get("steps", [])
    accent = spec.get("accent", "#093824")

    step_height = 72
    header_h = 44 if title else 16
    height = header_h + len(steps) * step_height + 20

    title_svg = f'  <text x="280" y="28" font-family="sans-serif" font-size="16" font-weight="700" fill="#111827" text-anchor="middle">{_esc(title)}</text>\n' if title else ""

    steps_svg = ""
    for i, step in enumerate(steps):
        y = header_h + i * step_height
        num = str(i + 1)
        step_title = _esc(step.get("title", f"Step {num}"))
        desc_lines = _wrap_text(step.get("description", ""), 52)

        # Connector line (not after last step)
        if i < len(steps) - 1:
            steps_svg += f'  <line x1="40" y1="{y + 34}" x2="40" y2="{y + step_height}" stroke="{accent}" stroke-width="2" opacity="0.3"/>\n'

        steps_svg += f'  <circle cx="40" cy="{y + 18}" r="18" fill="{accent}"/>\n'
        steps_svg += f'  <text x="40" y="{y + 23}" font-family="sans-serif" font-size="14" font-weight="800" fill="#fff" text-anchor="middle">{_esc(num)}</text>\n'
        steps_svg += f'  <text x="72" y="{y + 14}" font-family="sans-serif" font-size="15" font-weight="700" fill="#111827">{step_title}</text>\n'
        for j, line in enumerate(desc_lines[:2]):
            steps_svg += f'  <text x="72" y="{y + 32 + j * 18}" font-family="sans-serif" font-size="13" fill="#6b7280">{_esc(line)}</text>\n'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" width="560" height="{height}">
  <rect width="560" height="{height}" rx="8" fill="#f9fafb"/>
{title_svg}{steps_svg}</svg>"""


# ── Renderer: quote_card ────────────────────────────────────────────────────

def render_quote_card(spec: dict) -> str:
    """
    spec keys:
      quote       — the quoted text
      attribution — name/source
      accent      — hex color
    """
    quote = spec.get("quote", "")
    attribution = spec.get("attribution", "")
    accent = spec.get("accent", "#093824")

    quote_lines = _wrap_text(quote, 52)
    height = max(140, 70 + len(quote_lines) * 28 + (30 if attribution else 0))

    quote_svg = ""
    for i, line in enumerate(quote_lines):
        quote_svg += f'  <text x="280" y="{80 + i * 28}" font-family="Georgia, serif" font-size="18" fill="#111827" font-style="italic" text-anchor="middle">{_esc(line)}</text>\n'

    attr_svg = ""
    if attribution:
        attr_y = 80 + len(quote_lines) * 28 + 10
        attr_svg = f'  <text x="280" y="{attr_y}" font-family="sans-serif" font-size="13" fill="#6b7280" text-anchor="middle">— {_esc(attribution)}</text>\n'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" width="560" height="{height}">
  <rect width="560" height="{height}" rx="8" fill="#f9fafb"/>
  <rect x="0" y="0" width="560" height="6" rx="3" fill="{accent}"/>
  <text x="32" y="56" font-family="Georgia, serif" font-size="64" fill="{accent}" opacity="0.25">"</text>
{quote_svg}{attr_svg}</svg>"""


# ── Dispatch ────────────────────────────────────────────────────────────────

RENDERERS = {
    "stat_callout": render_stat_callout,
    "comparison": render_comparison,
    "timeline": render_timeline,
    "process_steps": render_process_steps,
    "quote_card": render_quote_card,
}


def render_infographic(spec: dict) -> str:
    """Dispatch to the correct renderer based on spec['type']."""
    renderer_type = spec.get("type", "stat_callout")
    renderer = RENDERERS.get(renderer_type)
    if not renderer:
        available = ", ".join(RENDERERS.keys())
        raise ValueError(f"Unknown renderer type: {renderer_type!r}. Available: {available}")
    return renderer(spec)


def main():
    parser = argparse.ArgumentParser(description="Render an SVG infographic from a JSON spec.")
    parser.add_argument("--spec", required=True, help="Path to the JSON spec file")
    parser.add_argument("--output", required=True, help="Output .svg file path")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    svg_content = render_infographic(spec)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg_content, encoding="utf-8")

    print(f"Infographic saved to: {out_path}")


if __name__ == "__main__":
    main()
