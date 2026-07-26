"""Report generation service.

Renders the run's touched opportunities into an HTML report, then a PDF
attachment, using only open-source libraries (Jinja2 + WeasyPrint) - no paid
rendering service required.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import Opportunity

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _fmt_money(value) -> str | None:
    if value is None:
        return None
    return f"R{value:,.2f}"


def _opportunity_to_report_item(opp: Opportunity, is_new: bool) -> dict:
    score = opp.latest_score()
    contacts = ", ".join(
        filter(None, [c.organisation_name for c in opp.contacts])
    ) or None
    source_titles = ", ".join(
        filter(None, [sl.source_title or sl.raw_document.title for sl in opp.source_listings])
    ) or "N/A"

    prop = opp.property_
    erf_bits = []
    if prop:
        if prop.erf_number:
            erf_bits.append(f"Erf {prop.erf_number}")
        if prop.township:
            erf_bits.append(prop.township)
        if prop.portion_number and prop.farm_name:
            erf_bits.append(f"Portion {prop.portion_number} of Farm {prop.farm_name}")
        if prop.sectional_unit_number and prop.sectional_title_scheme:
            erf_bits.append(f"Unit {prop.sectional_unit_number}, {prop.sectional_title_scheme}")
    erf_description = " / ".join(erf_bits) or None

    return {
        "title": opp.title,
        "status": opp.status,
        "opportunity_type": opp.opportunity_type,
        "is_new": is_new,
        "opportunity_score": score.opportunity_score if score else 0,
        "risk_score": score.risk_score if score else 0,
        "completeness_score": score.completeness_score if score else 0,
        "address": prop.canonical_address if prop else None,
        "erf_description": erf_description,
        "municipality": opp.municipality,
        "province": opp.province,
        "auction_date": opp.auction_date.strftime("%d %B %Y") if opp.auction_date else None,
        "auction_time": opp.auction_time,
        "auction_venue": opp.auction_venue,
        "reserve_price": _fmt_money(opp.reserve_price),
        "case_number": opp.case_number,
        "contact": contacts,
        "extraction_confidence": opp.extraction_confidence,
        "risk_flags": [
            {"title": f.title, "description": f.description, "severity": f.severity}
            for f in sorted(opp.risk_flags, key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}[f.severity])
        ],
        "source_titles": source_titles,
    }


def render_report(
    opportunities_with_flags: list[tuple[Opportunity, bool]],
    run_summary: dict,
    output_dir: Path | None = None,
) -> tuple[str, Path | None]:
    """opportunities_with_flags: list of (Opportunity, is_new). Returns
    (html_string, pdf_path). pdf_path is None if PDF rendering isn't
    available in this environment (report is still emailed as HTML)."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.j2")

    tz = ZoneInfo(settings.default_timezone)
    generated_at = datetime.now(UTC).astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")

    items = [
        _opportunity_to_report_item(opp, is_new)
        for opp, is_new in sorted(
            opportunities_with_flags,
            key=lambda pair: (pair[1] is False, -(pair[0].latest_score().opportunity_score if pair[0].latest_score() else 0)),
        )
    ]

    html = template.render(
        report_title="South African Distressed Property Opportunity Report",
        generated_at=generated_at,
        opportunities=items,
        run_summary=run_summary,
    )

    pdf_path = None
    output_dir = output_dir or settings.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        from weasyprint import HTML

        pdf_path = output_dir / f"report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.pdf"
        HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf(str(pdf_path))
    except Exception:
        pdf_path = None

    return html, pdf_path
