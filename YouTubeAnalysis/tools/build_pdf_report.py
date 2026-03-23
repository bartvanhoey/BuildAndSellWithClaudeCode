"""
build_pdf_report.py
Generates a branded Canvas Design PDF report from the analysis JSON.
Aesthetic philosophy: "Signal Intelligence" — the visual language of systems
that detect meaning in noise. Deep navy, accent orange/teal/violet, sparse
clinical typography, generous white space. Charts are the art.

Usage:
    python tools/build_pdf_report.py
    python tools/build_pdf_report.py --input .tmp/analysis_2026-03-23.json
    python tools/build_pdf_report.py --date 2026-03-23

Reads:
    .tmp/analysis_YYYY-MM-DD.json  (from analyze_trends.py, with agent-written narrative)
    config.json                     (email_subject_template for report title)

Output (stdout): JSON summary
Writes:
    .tmp/charts/*.png               (intermediate chart images)
    .tmp/decks/youtube_trends_YYYY-MM-DD.pdf

Pages:
    1. Cover + Executive Summary
    2. Top 10 Trending Videos (table)
    3. View Velocity Chart
    4. Engagement Rate Chart
    5. Top Keywords Bar Chart
    6. Top Channels Table + Spotlights
    7. Transcript Themes
    8. Content Opportunity Gaps + Recommendations
    9. Back Cover
"""

import argparse
import json
import sys
import textwrap
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
CHARTS_DIR = TMP_DIR / "charts"
DECKS_DIR = TMP_DIR / "decks"
FONT_DIR = PROJECT_ROOT / ".claude" / "skills" / "canvas-design" / "canvas-fonts"

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader
except ImportError:
    print("ERROR: reportlab not installed. Run: pip install reportlab", file=sys.stderr)
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    print("ERROR: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = landscape(A4)   # ~841.9 x 595.3 points
MARGIN = 28
ACCENT_BAR_W = 8
FOOTER_H = 22


# ---------------------------------------------------------------------------
# Colors (r, g, b as 0-1 floats)
# ---------------------------------------------------------------------------

def rgb(hex_str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


BG_DEEP       = rgb("0F0F23")
BG_CARD       = rgb("1A1A35")
BG_CARD_ALT   = rgb("141426")
ACCENT_ORANGE = rgb("FF4500")
ACCENT_TEAL   = rgb("00C2A8")
ACCENT_VIOLET = rgb("795EC6")
WHITE         = rgb("FFFFFF")
TEXT_LIGHT    = rgb("F2F4F7")
TEXT_MID      = rgb("98A2B3")
GREEN_HI      = rgb("12B76A")
AMBER_HI      = rgb("FFAB00")
RED_HI        = rgb("F04438")


# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------

FONTS_REGISTERED = False

# Fallback mapping to built-in reportlab fonts if TTF files can't be loaded
_FONT_FALLBACKS = {
    "Serif-Bold":    "Times-Bold",
    "Serif-Regular": "Times-Roman",
    "Sans-Bold":     "Helvetica-Bold",
    "Sans-Regular":  "Helvetica",
    "Mono-Bold":     "Courier-Bold",
    "Mono-Regular":  "Courier",
}

# Resolved font names (alias -> actual name to pass to setFont)
_FONT_MAP = dict(_FONT_FALLBACKS)  # start with fallbacks, override with TTF if available


def register_fonts():
    global FONTS_REGISTERED
    if FONTS_REGISTERED:
        return
    pairs = [
        ("Serif-Bold",    "IBMPlexSerif-Bold.ttf"),
        ("Serif-Regular", "IBMPlexSerif-Regular.ttf"),
        ("Sans-Bold",     "InstrumentSans-Bold.ttf"),
        ("Sans-Regular",  "InstrumentSans-Regular.ttf"),
        ("Mono-Bold",     "IBMPlexMono-Bold.ttf"),
        ("Mono-Regular",  "IBMPlexMono-Regular.ttf"),
    ]
    any_loaded = False
    for alias, filename in pairs:
        path = FONT_DIR / filename
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(alias, str(path)))
                _FONT_MAP[alias] = alias   # TTF loaded — use it
                any_loaded = True
            except Exception:
                pass  # silently fall back to built-in
    if not any_loaded:
        print("INFO: Canvas fonts unavailable — using built-in PDF fonts (Helvetica/Times/Courier)",
              file=sys.stderr)
    FONTS_REGISTERED = True


def F(alias: str) -> str:
    """Resolve a font alias to its actual registered name."""
    return _FONT_MAP.get(alias, "Helvetica")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def find_analysis(target_date: str | None) -> Path:
    if target_date:
        p = TMP_DIR / f"analysis_{target_date}.json"
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)
        return p
    candidates = sorted(TMP_DIR.glob("analysis_*.json"), reverse=True)
    if not candidates:
        print("ERROR: No analysis_*.json found in .tmp/ — run analyze_trends.py first", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def find_logo() -> Path | None:
    candidates = [
        PROJECT_ROOT / "AIS_Logo.png",
        PROJECT_ROOT.parent / "AIS_Logo.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def fmt_number(n: int | float) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def truncate(s: str, max_len: int) -> str:
    return s[:max_len] + "…" if len(s) > max_len else s


def set_fill(c, color):
    c.setFillColorRGB(*color)


def set_stroke(c, color):
    c.setStrokeColorRGB(*color)


def filled_rect(c, x, y, w, h, color):
    """Draw filled rect. y is from bottom (ReportLab convention)."""
    set_fill(c, color)
    c.setLineWidth(0)
    c.rect(x, y, w, h, stroke=0, fill=1)


def draw_text(c, x, y, text, font, size, color=WHITE, align="left"):
    """Draw single-line text. y is from bottom. font is a font alias or name."""
    c.setFont(F(font), size)
    set_fill(c, color)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def draw_wrapped_text(c, x, y, width, text, font, size, color=WHITE, line_height=None):
    """Draw word-wrapped text block. y is top of the text block (from bottom)."""
    if line_height is None:
        line_height = size * 1.45
    c.setFont(F(font), size)
    set_fill(c, color)
    # Estimate chars per line
    avg_char_width = size * 0.52
    chars_per_line = max(10, int(width / avg_char_width))
    lines = textwrap.wrap(text, width=chars_per_line)
    cur_y = y
    for line in lines:
        c.drawString(x, cur_y, line)
        cur_y -= line_height
    return cur_y  # returns y position after last line


def draw_accent_bar(c, color, width=ACCENT_BAR_W):
    filled_rect(c, 0, FOOTER_H, width, PAGE_H - FOOTER_H, color)


def draw_footer(c, run_date, logo_path, page_num):
    """Bottom footer strip with thin rule, page number, date, logo stamp."""
    # Footer background
    filled_rect(c, 0, 0, PAGE_W, FOOTER_H, BG_CARD_ALT if hasattr(BG_CARD_ALT, '__len__') else BG_DEEP)

    # Thin rule above footer
    set_stroke(c, TEXT_MID)
    c.setLineWidth(0.4)
    c.line(MARGIN, FOOTER_H, PAGE_W - MARGIN, FOOTER_H)

    footer_text_y = 6

    # Page number (left)
    draw_text(c, MARGIN + ACCENT_BAR_W + 4, footer_text_y,
              f"Page {page_num}", "Mono-Regular", 7, TEXT_MID)

    # Date (center)
    draw_text(c, PAGE_W / 2, footer_text_y,
              f"AI & Automation YouTube Trends — {run_date}",
              "Mono-Regular", 7, TEXT_MID, align="center")

    # Logo stamp (right)
    if logo_path and logo_path.exists():
        logo_h = 14
        logo_w = 40
        try:
            c.drawImage(str(logo_path), PAGE_W - MARGIN - logo_w, 3,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass


def draw_section_header(c, title, subtitle, accent_color):
    """Draw page title and subtitle below the accent bar region."""
    title_y = PAGE_H - MARGIN - 18
    draw_text(c, MARGIN + ACCENT_BAR_W + 8, title_y,
              title, "Serif-Bold", 22, WHITE)
    draw_text(c, MARGIN + ACCENT_BAR_W + 8, title_y - 16,
              subtitle, "Sans-Regular", 9, TEXT_MID)
    # Thin rule under subtitle
    set_stroke(c, accent_color)
    c.setLineWidth(0.8)
    rule_y = title_y - 22
    c.line(MARGIN + ACCENT_BAR_W + 8, rule_y, PAGE_W - MARGIN, rule_y)
    return rule_y - 8   # returns content start y


def save_chart_png(labels, values, color_hex, value_fmt_fn, filename, figsize=(10, 4.5)):
    """Save horizontal bar chart to .tmp/charts/ and return Path."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / filename
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#0F0F23")
    ax.set_facecolor("#1A1A35")

    y_pos = range(len(labels))
    bars = ax.barh(list(y_pos), values, color=color_hex, height=0.6, zorder=3)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color="white", fontsize=8)
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#333355")
    ax.spines["bottom"].set_color("#333355")
    ax.tick_params(colors="#888899", labelsize=8)
    ax.grid(axis="x", color="#333355", linestyle="--", alpha=0.5, zorder=0)
    for bar, val in zip(bars, values):
        label = value_fmt_fn(val) if value_fmt_fn else str(val)
        ax.text(bar.get_width() + max(values) * 0.01 if max(values) > 0 else 0.05,
                bar.get_y() + bar.get_height() / 2,
                label, va="center", ha="left", color="white", fontsize=7)
    plt.tight_layout()
    fig.savefig(str(path), format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def save_keywords_chart(keyword_freq, run_date):
    """Two-tone keywords chart."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / f"keywords_{run_date}.png"
    items = list(keyword_freq.items())[:20]
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    if not values:
        return None
    median_val = sorted(values)[len(values) // 2]
    colors = ["#795EC6" if v > median_val else "#4A3A80" for v in values]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor("#0F0F23")
    ax.set_facecolor("#1A1A35")
    y_pos = range(len(labels))
    bars = ax.barh(list(y_pos), values, color=colors, height=0.6, zorder=3)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color="white", fontsize=9)
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#333355")
    ax.spines["bottom"].set_color("#333355")
    ax.tick_params(colors="#888899", labelsize=8)
    ax.grid(axis="x", color="#333355", linestyle="--", alpha=0.5, zorder=0)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + max(values) * 0.01 if max(values) > 0 else 0.05,
                bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", color="white", fontsize=8)
    legend_patches = [
        mpatches.Patch(color="#795EC6", label=f"Above median ({median_val} mentions)"),
        mpatches.Patch(color="#4A3A80", label="At or below median"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", framealpha=0.3,
              labelcolor="white", fontsize=8)
    plt.tight_layout()
    fig.savefig(str(path), format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def build_cover(c, analysis, logo_path, run_date, page_num):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)
    draw_accent_bar(c, ACCENT_ORANGE)

    content_x = MARGIN + ACCENT_BAR_W + 16

    # Logo — top right
    if logo_path and logo_path.exists():
        logo_w = 160
        logo_h = 60
        try:
            c.drawImage(str(logo_path), PAGE_W - MARGIN - logo_w, PAGE_H - MARGIN - logo_h,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Title block
    draw_text(c, content_x, PAGE_H - MARGIN - 22, "AI & Automation",
              "Serif-Bold", 36, WHITE)
    draw_text(c, content_x, PAGE_H - MARGIN - 52, "YouTube Trend Report",
              "Sans-Regular", 20, ACCENT_ORANGE)
    draw_text(c, content_x, PAGE_H - MARGIN - 72,
              f"Week of {analysis.get('generated_date', run_date)}",
              "Mono-Regular", 10, TEXT_MID)

    # Divider line
    set_stroke(c, ACCENT_ORANGE)
    c.setLineWidth(0.8)
    c.line(content_x, PAGE_H - MARGIN - 82, PAGE_W - MARGIN, PAGE_H - MARGIN - 82)

    # KPI callout boxes (3 boxes)
    stats = [
        (fmt_number(analysis.get("total_videos_analyzed", 0)), "Videos Analyzed"),
        (f"{analysis.get('period_days', 14)} days", "Data Period"),
        (fmt_number(analysis.get("fastest_growing_video", {}).get("view_velocity", 0)) + "/day",
         "Top View Velocity"),
    ]
    box_w = 148
    box_h = 58
    box_top = PAGE_H - MARGIN - 158
    box_spacing = 12
    for i, (val, label) in enumerate(stats):
        bx = content_x + i * (box_w + box_spacing)
        filled_rect(c, bx, box_top, box_w, box_h, BG_CARD)
        draw_text(c, bx + box_w / 2, box_top + box_h - 22, val,
                  "Mono-Bold", 20, ACCENT_ORANGE, align="center")
        draw_text(c, bx + box_w / 2, box_top + 8, label,
                  "Sans-Regular", 8, TEXT_MID, align="center")

    # Executive summary
    summary = analysis.get("executive_summary", "")
    if summary:
        summary_y = box_top - 20
        draw_text(c, content_x, summary_y, "Executive Summary",
                  "Sans-Bold", 9, ACCENT_ORANGE)
        draw_wrapped_text(c, content_x, summary_y - 14,
                          PAGE_W - content_x - MARGIN - 10,
                          summary, "Sans-Regular", 9, TEXT_LIGHT, line_height=14)

    draw_footer(c, run_date, logo_path, page_num)


def build_top_videos(c, analysis, logo_path, run_date, page_num):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)
    draw_accent_bar(c, ACCENT_ORANGE)
    content_y = draw_section_header(c, "Top 10 Trending Videos",
                                    f"Sorted by view count · Past {analysis.get('period_days', 14)} days",
                                    ACCENT_ORANGE)

    top_videos = analysis.get("top_videos", [])[:10]
    table_x = MARGIN + ACCENT_BAR_W + 4
    table_w = PAGE_W - table_x - MARGIN

    cols = ["#", "Title", "Channel", "Views", "Engagement", "Published"]
    col_ratios = [0.03, 0.38, 0.20, 0.10, 0.13, 0.11]
    col_widths = [table_w * r for r in col_ratios]
    row_h = 22

    # Header row
    filled_rect(c, table_x, content_y - row_h, table_w, row_h, ACCENT_ORANGE)
    cx = table_x + 4
    for col, cw in zip(cols, col_widths):
        draw_text(c, cx, content_y - row_h + 7, col, "Sans-Bold", 8, WHITE)
        cx += cw

    # Data rows
    for row_idx, video in enumerate(top_videos):
        row_y = content_y - row_h * (row_idx + 2)
        row_color = BG_CARD if row_idx % 2 == 0 else BG_CARD_ALT
        filled_rect(c, table_x, row_y, table_w, row_h, row_color)

        eng = video.get("engagement_rate", 0)
        eng_color = GREEN_HI if eng >= 3 else (AMBER_HI if eng >= 1 else RED_HI)

        cells = [
            (str(row_idx + 1), TEXT_MID),
            (truncate(video.get("title", ""), 52), TEXT_LIGHT),
            (truncate(video.get("channel_title", ""), 28), TEXT_MID),
            (fmt_number(video.get("view_count", 0)), WHITE),
            (f"{eng:.1f}%", eng_color),
            (video.get("published_at", "")[:10], TEXT_MID),
        ]
        cx = table_x + 4
        for (cell_text, cell_color), cw in zip(cells, col_widths):
            draw_text(c, cx, row_y + 7, cell_text, "Sans-Regular", 7.5, cell_color)
            cx += cw

    # Legend
    legend_y = content_y - row_h * (len(top_videos) + 2) - 6
    draw_text(c, table_x, legend_y,
              "Engagement = (Likes + Comments) / Views × 100.  Green >3%  Amber 1-3%  Red <1%",
              "Mono-Regular", 7, TEXT_MID)

    draw_footer(c, run_date, logo_path, page_num)


def build_chart_page(c, analysis, logo_path, run_date, page_num,
                     title, subtitle, accent_color, chart_path):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)
    draw_accent_bar(c, accent_color)
    content_y = draw_section_header(c, title, subtitle, accent_color)

    if chart_path and Path(chart_path).exists():
        img_x = MARGIN + ACCENT_BAR_W + 4
        img_y = FOOTER_H + 4
        img_w = PAGE_W - img_x - MARGIN
        img_h = content_y - FOOTER_H - 12
        try:
            c.drawImage(str(chart_path), img_x, img_y, width=img_w, height=img_h,
                        preserveAspectRatio=True, anchor="sw")
        except Exception as e:
            draw_text(c, img_x, img_y + img_h / 2,
                      f"Chart unavailable: {e}", "Sans-Regular", 10, TEXT_MID)
    else:
        draw_text(c, MARGIN + ACCENT_BAR_W + 20, PAGE_H / 2,
                  "No data available for this chart.", "Sans-Regular", 12, TEXT_MID)

    draw_footer(c, run_date, logo_path, page_num)


def build_top_channels(c, analysis, logo_path, run_date, page_num):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)
    draw_accent_bar(c, ACCENT_ORANGE)
    content_y = draw_section_header(c, "Top Channels to Watch",
                                    "Ranked by total views in dataset this period",
                                    ACCENT_ORANGE)

    top_channels = analysis.get("top_channels", [])[:7]
    spotlights = analysis.get("channel_spotlights", [])

    table_x = MARGIN + ACCENT_BAR_W + 4
    table_w = PAGE_W - table_x - MARGIN
    cols = ["Channel", "Subscribers", "Videos", "Avg Views/Video", "Top Video"]
    col_ratios = [0.22, 0.13, 0.08, 0.15, 0.38]
    col_widths = [table_w * r for r in col_ratios]
    row_h = 22

    # Header
    filled_rect(c, table_x, content_y - row_h, table_w, row_h, ACCENT_ORANGE)
    cx = table_x + 4
    for col, cw in zip(cols, col_widths):
        draw_text(c, cx, content_y - row_h + 7, col, "Sans-Bold", 8, WHITE)
        cx += cw

    for row_idx, ch in enumerate(top_channels):
        row_y = content_y - row_h * (row_idx + 2)
        row_color = BG_CARD if row_idx % 2 == 0 else BG_CARD_ALT
        filled_rect(c, table_x, row_y, table_w, row_h, row_color)
        cells = [
            truncate(ch.get("title", ""), 32),
            fmt_number(ch.get("subscriber_count", 0)),
            str(ch.get("videos_in_dataset", 0)),
            fmt_number(ch.get("avg_views_per_video", 0)),
            truncate(ch.get("top_video_title", ""), 52),
        ]
        cx = table_x + 4
        for cell_text, cw in zip(cells, col_widths):
            draw_text(c, cx, row_y + 7, cell_text, "Sans-Regular", 7.5, TEXT_LIGHT)
            cx += cw

    # Spotlights section
    spot_top = content_y - row_h * (len(top_channels) + 2) - 14
    if spotlights and spot_top > FOOTER_H + 60:
        draw_text(c, table_x, spot_top, "Channel Spotlights",
                  "Sans-Bold", 9, ACCENT_ORANGE)
        sp_top = spot_top - 14
        sp_box_w = (table_w - 16) / 3
        for i, spotlight in enumerate(spotlights[:3]):
            sp_x = table_x + i * (sp_box_w + 8)
            sp_h = max(36, sp_top - FOOTER_H - 10)
            sp_h = min(sp_h, 50)
            filled_rect(c, sp_x, sp_top - sp_h, sp_box_w, sp_h, BG_CARD)
            text = spotlight if isinstance(spotlight, str) else spotlight.get("text", str(spotlight))
            draw_wrapped_text(c, sp_x + 6, sp_top - 10,
                              sp_box_w - 12, text,
                              "Sans-Regular", 8, TEXT_LIGHT, line_height=12)

    draw_footer(c, run_date, logo_path, page_num)


def build_transcript_themes(c, analysis, logo_path, run_date, page_num):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)
    draw_accent_bar(c, ACCENT_TEAL)
    content_y = draw_section_header(
        c, "Transcript Theme Analysis",
        "Topics creators are actually discussing — extracted from video transcripts (n-gram frequency)",
        ACCENT_TEAL)

    themes = analysis.get("transcript_themes", [])
    table_x = MARGIN + ACCENT_BAR_W + 4
    content_h = content_y - FOOTER_H - 10

    if not themes:
        draw_text(c, table_x, content_y - 40,
                  "No transcript data available for this run.",
                  "Sans-Regular", 12, TEXT_MID)
        draw_footer(c, run_date, logo_path, page_num)
        return

    left_w = (PAGE_W - table_x - MARGIN) * 0.50
    right_x = table_x + left_w + 16
    right_w = PAGE_W - right_x - MARGIN

    # Left: ranked topics with inline bars
    draw_text(c, table_x, content_y - 2, "Top Discussed Topics",
              "Sans-Bold", 10, WHITE)
    max_count = themes[0]["count"] if themes else 1
    bar_area_w = left_w - 60
    item_h = min(22, content_h / max(len(themes[:15]), 1))

    for i, theme in enumerate(themes[:15]):
        item_y = content_y - 18 - i * item_h
        if item_y < FOOTER_H + 10:
            break
        bar_fill_w = max(4, bar_area_w * (theme["count"] / max_count))
        filled_rect(c, table_x, item_y - item_h + 4, bar_area_w, item_h - 4, BG_CARD)
        filled_rect(c, table_x, item_y - item_h + 4, bar_fill_w, item_h - 4, rgb("008068"))
        draw_text(c, table_x + 4, item_y - item_h + 8,
                  f"{i+1}. {theme['phrase']}", "Sans-Regular", 8, WHITE)
        draw_text(c, table_x + bar_area_w + 2, item_y - item_h + 8,
                  str(theme["count"]), "Mono-Regular", 7, TEXT_MID)

    # Right: context note
    draw_text(c, right_x, content_y - 2, "What This Means",
              "Sans-Bold", 10, WHITE)
    note = (
        "These phrases appear most frequently across all analyzed transcripts. "
        "They represent what creators are actually teaching and discussing — "
        "not just what they promise in titles. "
        "Cross-reference with the Keywords page to find gaps between what's "
        "titled vs. what's being taught. Those gaps are your content opportunities."
    )
    filled_rect(c, right_x, FOOTER_H + 20, right_w, content_y - FOOTER_H - 36, BG_CARD)
    draw_wrapped_text(c, right_x + 8, content_y - 20,
                      right_w - 16, note,
                      "Sans-Regular", 9, TEXT_LIGHT, line_height=14)

    draw_footer(c, run_date, logo_path, page_num)


def build_content_gaps(c, analysis, logo_path, run_date, page_num):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)
    draw_accent_bar(c, ACCENT_VIOLET)
    content_y = draw_section_header(
        c, "Content Opportunity Gaps",
        "Topics discussed in transcripts but absent from video titles — potential underserved niches",
        ACCENT_VIOLET)

    gaps = analysis.get("content_gaps", [])
    recommendations = analysis.get("recommendations", [])
    table_x = MARGIN + ACCENT_BAR_W + 4
    half_w = (PAGE_W - table_x - MARGIN - 12) / 2

    # Left panel: gaps
    draw_text(c, table_x, content_y - 2, "Topics in Transcripts, Not in Titles",
              "Sans-Bold", 10, ACCENT_TEAL)
    set_stroke(c, ACCENT_TEAL)
    c.setLineWidth(2)
    c.line(table_x, content_y - 8, table_x, FOOTER_H + 12)

    if gaps:
        for i, gap in enumerate(gaps[:10]):
            gy = content_y - 18 - i * 28
            if gy < FOOTER_H + 20:
                break
            filled_rect(c, table_x + 4, gy - 18, half_w - 8, 22, BG_CARD_ALT)
            draw_text(c, table_x + 10, gy - 11, f"• {gap}",
                      "Sans-Regular", 9, TEXT_LIGHT)
    else:
        draw_text(c, table_x + 10, content_y - 30,
                  "No gaps detected — transcript coverage may be limited.",
                  "Sans-Regular", 9, TEXT_MID)

    # Right panel: recommendations
    right_x = table_x + half_w + 12
    draw_text(c, right_x, content_y - 2, "Recommended Video Ideas",
              "Sans-Bold", 10, ACCENT_ORANGE)
    set_stroke(c, ACCENT_ORANGE)
    c.setLineWidth(2)
    c.line(right_x, content_y - 8, right_x, FOOTER_H + 12)

    if recommendations:
        rec_list = recommendations if isinstance(recommendations, list) else [recommendations]
        for i, rec in enumerate(rec_list[:7]):
            ry = content_y - 18 - i * 34
            if ry < FOOTER_H + 24:
                break
            filled_rect(c, right_x + 4, ry - 24, half_w - 8, 28, BG_CARD)
            text = rec if isinstance(rec, str) else rec.get("title", str(rec))
            draw_wrapped_text(c, right_x + 10, ry - 8, half_w - 20,
                              text, "Sans-Regular", 8.5, TEXT_LIGHT, line_height=12)
    else:
        draw_text(c, right_x + 10, content_y - 30,
                  "No recommendations written yet.",
                  "Sans-Regular", 9, TEXT_MID)

    # Source footer note
    src_text = (f"Generated {analysis.get('generated_date', '')} | "
                f"Data period: past {analysis.get('period_days', 14)} days | "
                "Sources: YouTube Data API v3 + youtube-transcript-api")
    draw_text(c, table_x, FOOTER_H + 4, src_text, "Mono-Regular", 6.5, TEXT_MID)

    draw_footer(c, run_date, logo_path, page_num)


def build_back_cover(c, logo_path, run_date, page_num):
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, BG_DEEP)

    # Geometric accent elements
    filled_rect(c, 0, 0, PAGE_W, 6, ACCENT_ORANGE)
    filled_rect(c, 0, PAGE_H - 6, PAGE_W, 6, ACCENT_ORANGE)
    filled_rect(c, 0, 0, 6, PAGE_H, ACCENT_ORANGE)
    filled_rect(c, PAGE_W - 6, 0, 6, PAGE_H, ACCENT_ORANGE)

    center_x = PAGE_W / 2
    center_y = PAGE_H / 2

    # Large centered logo
    if logo_path and logo_path.exists():
        logo_w = 200
        logo_h = 80
        try:
            c.drawImage(str(logo_path), center_x - logo_w / 2, center_y + 20,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Thin divider
    set_stroke(c, ACCENT_ORANGE)
    c.setLineWidth(0.8)
    c.line(center_x - 120, center_y + 14, center_x + 120, center_y + 14)

    draw_text(c, center_x, center_y - 2,
              "AI & Automation Intelligence System",
              "Serif-Bold", 16, WHITE, align="center")
    draw_text(c, center_x, center_y - 22,
              "Powered by YouTube Data API v3 · youtube-transcript-api · Claude AI",
              "Sans-Regular", 9, TEXT_MID, align="center")
    draw_text(c, center_x, center_y - 40,
              f"Report generated: {run_date}",
              "Mono-Regular", 9, TEXT_MID, align="center")

    # Bottom tag
    draw_text(c, center_x, FOOTER_H + 8,
              "CONFIDENTIAL — For internal team distribution only",
              "Mono-Regular", 7.5, TEXT_MID, align="center")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build YouTube trends branded PDF report")
    parser.add_argument("--input", help="Path to analysis JSON (overrides --date)")
    parser.add_argument("--date", help="Date label YYYY-MM-DD (default: most recent)")
    args = parser.parse_args()

    if args.input:
        analysis_path = Path(args.input)
        if not analysis_path.exists():
            print(f"ERROR: {analysis_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        analysis_path = find_analysis(args.date)

    run_date = analysis_path.stem.replace("analysis_", "") or date.today().isoformat()
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    DECKS_DIR.mkdir(parents=True, exist_ok=True)

    register_fonts()
    logo_path = find_logo()
    if not logo_path:
        print("WARNING: AIS_Logo.png not found — logo will be omitted", file=sys.stderr)

    output_path = DECKS_DIR / f"youtube_trends_{run_date}.pdf"
    pdf = rl_canvas.Canvas(str(output_path), pagesize=landscape(A4))

    # Page 1: Cover
    print("  Building page 1: Cover...", file=sys.stderr)
    build_cover(pdf, analysis, logo_path, run_date, 1)
    pdf.showPage()

    # Page 2: Top Videos
    print("  Building page 2: Top Videos...", file=sys.stderr)
    build_top_videos(pdf, analysis, logo_path, run_date, 2)
    pdf.showPage()

    # Page 3: View Velocity chart
    print("  Building page 3: View Velocity...", file=sys.stderr)
    ranking = analysis.get("view_velocity_ranking", [])[:12]
    if ranking:
        labels = [truncate(f"{v.get('channel_title', '')} — {v.get('title', '')}", 60) for v in ranking]
        values = [v.get("view_velocity", 0) for v in ranking]
        chart_path = save_chart_png(labels, values, "#FF4500",
                                    lambda v: f"{fmt_number(v)}/d",
                                    f"velocity_{run_date}.png")
    else:
        chart_path = None
    build_chart_page(pdf, analysis, logo_path, run_date, 3,
                     "View Velocity Ranking",
                     "Views ÷ Days Since Publish — normalises for age, reveals what's actually growing now",
                     ACCENT_TEAL, chart_path)
    pdf.showPage()

    # Page 4: Engagement Rate chart
    print("  Building page 4: Engagement Rate...", file=sys.stderr)
    eng_ranking = analysis.get("engagement_ranking", [])[:12]
    if eng_ranking:
        labels = [truncate(v.get("title", ""), 60) for v in eng_ranking]
        values = [v.get("engagement_rate", 0) for v in eng_ranking]
        chart_path = save_chart_png(labels, values, "#00C2A8",
                                    lambda v: f"{v:.1f}%",
                                    f"engagement_{run_date}.png")
    else:
        chart_path = None
    build_chart_page(pdf, analysis, logo_path, run_date, 4,
                     "Engagement Rate Ranking",
                     f"Top videos by engagement rate. High engagement signals algorithmic boost.",
                     ACCENT_TEAL, chart_path)
    pdf.showPage()

    # Page 5: Keywords chart
    print("  Building page 5: Keywords...", file=sys.stderr)
    keyword_freq = analysis.get("keyword_frequency", {})
    kw_chart_path = save_keywords_chart(keyword_freq, run_date) if keyword_freq else None
    build_chart_page(pdf, analysis, logo_path, run_date, 5,
                     "Top Keywords in Video Titles",
                     "Most frequent words across all discovered titles this period (stop words excluded)",
                     ACCENT_VIOLET, kw_chart_path)
    pdf.showPage()

    # Page 6: Top Channels
    print("  Building page 6: Top Channels...", file=sys.stderr)
    build_top_channels(pdf, analysis, logo_path, run_date, 6)
    pdf.showPage()

    # Page 7: Transcript Themes
    print("  Building page 7: Transcript Themes...", file=sys.stderr)
    build_transcript_themes(pdf, analysis, logo_path, run_date, 7)
    pdf.showPage()

    # Page 8: Content Gaps
    print("  Building page 8: Content Gaps...", file=sys.stderr)
    build_content_gaps(pdf, analysis, logo_path, run_date, 8)
    pdf.showPage()

    # Page 9: Back Cover
    print("  Building page 9: Back Cover...", file=sys.stderr)
    build_back_cover(pdf, logo_path, run_date, 9)
    pdf.showPage()

    pdf.save()

    if not output_path.exists() or output_path.stat().st_size == 0:
        print("ERROR: PDF file was not written or is empty.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({
        "status": "ok",
        "date": run_date,
        "pages": 9,
        "output": str(output_path),
        "file_size_kb": round(output_path.stat().st_size / 1024, 1),
    }, indent=2))


if __name__ == "__main__":
    main()
