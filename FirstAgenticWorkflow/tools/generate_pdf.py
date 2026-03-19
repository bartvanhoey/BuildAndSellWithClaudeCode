"""
generate_pdf.py
Builds a branded competitor analysis PDF from .tmp/report_data_YYYY-MM-DD.json.

Usage:
    python tools/generate_pdf.py
    python tools/generate_pdf.py --date 2026-03-19
    python tools/generate_pdf.py --input /path/to/report_data.json

Requires:
    .tmp/brand_config.json     (from parse_brand_assets.py)
    .tmp/report_data_*.json    (from assemble_report_data.py)
    Pillow, reportlab

Output: .tmp/competitor_report_YYYY-MM-DD.pdf
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.flowables import HRFlowable
except ImportError:
    print("ERROR: reportlab not installed. Run: pip install reportlab Pillow", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hex_to_color(hex_str: str):
    """Convert '#093824' to a ReportLab Color."""
    hex_str = hex_str.lstrip("#")
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return colors.Color(r / 255, g / 255, b / 255)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_report_data(target_date: str | None) -> Path:
    if target_date:
        p = TMP_DIR / f"report_data_{target_date}.json"
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)
        return p
    # Find most recent
    candidates = sorted(TMP_DIR.glob("report_data_*.json"), reverse=True)
    if not candidates:
        print("ERROR: No report_data_*.json found in .tmp/", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


# ---------------------------------------------------------------------------
# Page template (header/footer on every page)
# ---------------------------------------------------------------------------

class BrandedDocTemplate(SimpleDocTemplate):
    def __init__(self, *args, brand: dict, company_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.brand = brand
        self.company_name = company_name
        self._primary = hex_to_color(brand.get("primary_color", "#093824"))
        self._secondary = hex_to_color(brand.get("secondary_color", "#c0652a"))

    def handle_pageBegin(self):
        super().handle_pageBegin()

    def afterPage(self):
        """Draw footer on every page after the cover."""
        canvas = self.canv
        if canvas.getPageNumber() <= 1:
            return
        canvas.saveState()
        secondary = hex_to_color(self.brand.get("secondary_color", "#c0652a"))
        canvas.setFillColor(secondary)
        canvas.setFont("Helvetica", 8)
        w, h = A4
        # Left: company name
        canvas.drawString(2 * cm, 1.2 * cm, self.company_name)
        # Right: page number
        page_str = f"Page {canvas.getPageNumber()}"
        canvas.drawRightString(w - 2 * cm, 1.2 * cm, page_str)
        # Rule above footer
        canvas.setStrokeColor(secondary)
        canvas.setLineWidth(0.5)
        canvas.line(2 * cm, 1.6 * cm, w - 2 * cm, 1.6 * cm)
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Style factory
# ---------------------------------------------------------------------------

def make_styles(primary_color, secondary_color) -> dict:
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_title"] = ParagraphStyle(
        "cover_title",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=primary_color,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    styles["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle",
        fontName="Helvetica",
        fontSize=14,
        textColor=colors.HexColor("#475467"),
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    styles["section_heading"] = ParagraphStyle(
        "section_heading",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=primary_color,
        spaceBefore=18,
        spaceAfter=8,
    )
    styles["competitor_heading"] = ParagraphStyle(
        "competitor_heading",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=secondary_color,
        spaceBefore=14,
        spaceAfter=6,
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#1d2939"),
        spaceAfter=6,
        leading=14,
    )
    styles["bullet"] = ParagraphStyle(
        "bullet",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#344054"),
        leftIndent=12,
        spaceAfter=3,
        leading=13,
    )
    styles["table_header"] = ParagraphStyle(
        "table_header",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    styles["table_cell"] = ParagraphStyle(
        "table_cell",
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#1d2939"),
        leading=11,
    )
    return styles


# ---------------------------------------------------------------------------
# Content builders
# ---------------------------------------------------------------------------

def build_cover(brand: dict, report: dict, styles: dict) -> list:
    elements = []
    w, _ = A4
    primary = hex_to_color(brand.get("primary_color", "#093824"))

    # Logo
    logo_path = brand.get("logo_path")
    if logo_path and Path(logo_path).exists():
        try:
            img = Image(logo_path, width=5 * cm, height=2.5 * cm, kind="proportional")
            img.hAlign = "CENTER"
            elements.append(Spacer(1, 2 * cm))
            elements.append(img)
            elements.append(Spacer(1, 1.5 * cm))
        except Exception:
            elements.append(Spacer(1, 4 * cm))
    else:
        elements.append(Spacer(1, 4 * cm))

    company_name = report.get("company", {}).get("company_name", "")
    gen_date = report.get("generated_date", date.today().isoformat())

    elements.append(Paragraph("Competitor Intelligence Report", styles["cover_title"]))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(company_name, styles["cover_subtitle"]))
    elements.append(Paragraph(gen_date, styles["cover_subtitle"]))
    elements.append(Spacer(1, 1 * cm))
    elements.append(HRFlowable(width="80%", thickness=2, color=primary, hAlign="CENTER"))
    elements.append(PageBreak())
    return elements


def build_executive_summary(report: dict, styles: dict) -> list:
    elements = []
    elements.append(Paragraph("Executive Summary", styles["section_heading"]))
    elements.append(HRFlowable(width="100%", thickness=1,
                                color=hex_to_color("#e4e7ec"), hAlign="LEFT"))
    elements.append(Spacer(1, 0.3 * cm))

    summary = report.get("executive_summary", "No executive summary provided.")
    for para in summary.split("\n\n"):
        para = para.strip()
        if para:
            elements.append(Paragraph(para, styles["body"]))
    elements.append(PageBreak())
    return elements


def summarize_field(data: dict | list | str | None, max_chars: int = 200) -> str:
    """Flatten a field to a short string for table cells."""
    if data is None:
        return "—"
    if isinstance(data, str):
        return data[:max_chars] + ("…" if len(data) > max_chars else "")
    if isinstance(data, list):
        if not data:
            return "—"
        parts = []
        for item in data:
            if isinstance(item, dict):
                parts.append(item.get("title") or item.get("text") or str(item))
            else:
                parts.append(str(item))
        joined = "; ".join(parts[:3])
        return joined[:max_chars] + ("…" if len(joined) > max_chars else "")
    if isinstance(data, dict):
        notes = data.get("notes") or data.get("text") or ""
        if notes:
            return notes[:max_chars]
        return str(data)[:max_chars]
    return str(data)[:max_chars]


def build_competitor_section(competitor: dict, styles: dict, primary, secondary) -> list:
    elements = []
    name = competitor.get("name", "Unknown")
    domain = competitor.get("domain", "")

    elements.append(Paragraph(f"{name}  ({domain})", styles["competitor_heading"]))

    # Summary table: 4 columns
    pricing_summary = summarize_field(competitor.get("pricing"))
    messaging_summary = summarize_field(competitor.get("messaging"))
    seo_summary = summarize_field(competitor.get("seo"))
    news_items = competitor.get("news", [])
    news_summary = summarize_field(news_items if news_items else "No activity past 7 days")

    headers = [
        Paragraph("Pricing", styles["table_header"]),
        Paragraph("Messaging", styles["table_header"]),
        Paragraph("SEO Signals", styles["table_header"]),
        Paragraph("Recent News", styles["table_header"]),
    ]
    row = [
        Paragraph(pricing_summary, styles["table_cell"]),
        Paragraph(messaging_summary, styles["table_cell"]),
        Paragraph(seo_summary, styles["table_cell"]),
        Paragraph(news_summary, styles["table_cell"]),
    ]

    col_width = (A4[0] - 4 * cm) / 4
    table = Table([headers, row], colWidths=[col_width] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e4e7ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.4 * cm))

    # Expanded bullets
    def add_bullets(label: str, items: list[str]):
        if not items:
            return
        elements.append(Paragraph(f"<b>{label}</b>", styles["bullet"]))
        for item in items[:6]:
            if item and item != "—":
                elements.append(Paragraph(f"• {item}", styles["bullet"]))

    # Pricing details
    pricing = competitor.get("pricing", {})
    if isinstance(pricing, dict):
        pricing_lines = pricing.get("pricing_text") or pricing.get("raw_text") or []
        add_bullets("Pricing details:", pricing_lines[:8])
        if pricing.get("notes"):
            elements.append(Paragraph(f"<i>{pricing['notes']}</i>", styles["bullet"]))

    # Messaging details
    messaging = competitor.get("messaging", {})
    if isinstance(messaging, dict):
        h1s = messaging.get("h1", [])
        ctas = messaging.get("ctas", [])
        if h1s:
            add_bullets("Headlines:", h1s)
        if ctas:
            add_bullets("CTAs:", ctas)
        if messaging.get("meta_description"):
            elements.append(Paragraph(
                f"<i>Meta: {messaging['meta_description'][:160]}</i>", styles["bullet"]
            ))

    # News
    if news_items:
        elements.append(Paragraph("<b>News this week:</b>", styles["bullet"]))
        for article in news_items[:5]:
            if isinstance(article, dict):
                title = article.get("title", "")
                source = article.get("source", "")
                art_date = article.get("date", "")
                line = f"• {title}"
                if source or art_date:
                    line += f" — {source} {art_date}".strip()
                elements.append(Paragraph(line, styles["bullet"]))

    # Social
    social = competitor.get("social", {})
    if isinstance(social, dict):
        links = []
        if social.get("linkedin_url"):
            links.append(f"LinkedIn: {social['linkedin_url']}")
        if social.get("twitter_url"):
            links.append(f"Twitter/X: {social['twitter_url']}")
        if links:
            add_bullets("Social profiles:", links)

    # Scrape errors
    errors = competitor.get("scrape_errors", [])
    if errors:
        elements.append(Paragraph(
            f"<font color='#f04438'>⚠ Scrape errors: {', '.join(str(e) for e in errors)}</font>",
            styles["bullet"]
        ))

    elements.append(Spacer(1, 0.5 * cm))
    return elements


def build_competitors(report: dict, styles: dict, brand: dict) -> list:
    elements = []
    primary = hex_to_color(brand.get("primary_color", "#093824"))
    secondary = hex_to_color(brand.get("secondary_color", "#c0652a"))

    elements.append(Paragraph("Competitor Profiles", styles["section_heading"]))
    elements.append(HRFlowable(width="100%", thickness=1,
                                color=hex_to_color("#e4e7ec"), hAlign="LEFT"))
    elements.append(Spacer(1, 0.3 * cm))

    for comp in report.get("competitors", []):
        elements.extend(build_competitor_section(comp, styles, primary, secondary))

    return elements


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_pdf(report: dict, brand: dict, output_path: Path) -> Path:
    primary = hex_to_color(brand.get("primary_color", "#093824"))
    secondary = hex_to_color(brand.get("secondary_color", "#c0652a"))
    styles = make_styles(primary, secondary)
    company_name = report.get("company", {}).get("company_name", "")

    doc = BrandedDocTemplate(
        str(output_path),
        pagesize=A4,
        brand=brand,
        company_name=company_name,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
    )

    story = []
    story.extend(build_cover(brand, report, styles))
    story.extend(build_executive_summary(report, styles))
    story.extend(build_competitors(report, styles, brand))

    doc.build(story)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate competitor analysis PDF")
    parser.add_argument("--date", help="Report date YYYY-MM-DD (default: today)")
    parser.add_argument("--input", help="Path to report_data JSON (overrides --date)")
    args = parser.parse_args()

    # Load brand config
    brand_config_path = TMP_DIR / "brand_config.json"
    if not brand_config_path.exists():
        print("ERROR: .tmp/brand_config.json not found — run parse_brand_assets.py first", file=sys.stderr)
        sys.exit(1)
    brand = load_json(brand_config_path)

    # Load report data
    if args.input:
        report_path = Path(args.input)
        if not report_path.exists():
            print(f"ERROR: {report_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        report_path = find_report_data(args.date)

    report = load_json(report_path)

    today = report.get("generated_date", date.today().isoformat())
    output_path = TMP_DIR / f"competitor_report_{today}.pdf"

    generate_pdf(report, brand, output_path)
    print(json.dumps({"status": "ok", "output": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
