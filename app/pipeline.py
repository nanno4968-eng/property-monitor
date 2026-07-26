"""Pipeline orchestrator (brief section 9): discover -> download -> extract ->
classify -> parse -> normalise -> deduplicate -> score -> review -> notify.

This is the single entry point the GitHub Actions workflow (and local `make
run`) calls. It is intentionally a plain synchronous script - no Celery/Redis
worker queue - because MVP volumes (a handful of manually-uploaded notices
per run) don't need one, and a worker queue would mean paying for an
always-on process. If volume grows, docs/architecture.md explains how to
swap this for Celery without touching the services layer.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.collectors.manual_upload import collect_from_inbox
from app.config import settings
from app.db import init_db, session_scope
from app.models import (
    AuditLog,
    Contact,
    Opportunity,
    Property,
    RiskFlag,
    Score,
    SourceListing,
)
from app.parsers.classify import classify_document
from app.parsers.sheriff_notice_parser import parse_sheriff_notice
from app.services import scoring
from app.services.dedup import CandidateFingerprint, classify_match, duplicate_score
from app.services.due_diligence import create_default_checklist
from app.services.emailer import send_report_email
from app.services.geocoding import geocode_address
from app.services.normalisation import (
    normalise_address,
    normalise_province,
    parse_price,
    parse_sa_date,
)
from app.services.report import render_report
from app.services.risk_engine import generate_risk_flags

TARGET_PROVINCES = {"gauteng"}  # brief section 2: Gauteng is the MVP target market


def _audit(session, entity_type: str, entity_id: str, action: str, detail: str | None = None) -> None:
    session.add(AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, detail=detail))


def _build_property(parsed, normalised_address: str | None, province: str | None, geocode) -> Property:
    erf = parsed.erf
    return Property(
        canonical_address=normalised_address,
        address_line_1=normalised_address,
        municipality=None,
        province=province,
        latitude=geocode.latitude,
        longitude=geocode.longitude,
        geocode_confidence=geocode.confidence,
        erf_number=erf.erf_number if erf else None,
        portion_number=erf.portion_number if erf else None,
        farm_number=erf.farm_number if erf else None,
        farm_name=erf.farm_name if erf else None,
        township=erf.township if erf else None,
        extension=erf.extension if erf else None,
        sectional_title_scheme=erf.sectional_title_scheme if erf else None,
        sectional_unit_number=erf.sectional_unit_number if erf else None,
        property_type="house" if (parsed.bedrooms or parsed.bathrooms) else "unknown",
        estimated_land_area_m2=parsed.land_area_m2,
    )


def _process_document(session, raw_doc) -> tuple[Opportunity | None, bool, str]:
    """Returns (opportunity_or_None, is_new, outcome_label)."""
    text = raw_doc.extracted_text or ""
    classification = classify_document(text)
    raw_doc.processing_status = "processed"

    if classification in ("unrelated", "estate_notice_only"):
        raw_doc.processing_status = "rejected_no_sale"
        _audit(session, "raw_document", raw_doc.id, "rejected", f"classification={classification}")
        return None, False, "rejected_no_sale"

    parsed = parse_sheriff_notice(text)

    auction_date = parse_sa_date(parsed.auction_date_raw)
    reserve_price = parse_price(parsed.reserve_price_raw)
    province = normalise_province(parsed.province)
    normalised_address = normalise_address(parsed.physical_address)
    geocode = geocode_address(normalised_address)

    fingerprint = CandidateFingerprint(
        case_number=parsed.case_number,
        erf_number=parsed.erf.erf_number if parsed.erf else None,
        township=parsed.erf.township if parsed.erf else None,
        sectional_unit_number=parsed.erf.sectional_unit_number if parsed.erf else None,
        sectional_title_scheme=parsed.erf.sectional_title_scheme if parsed.erf else None,
        normalised_address=normalised_address,
        latitude=geocode.latitude,
        longitude=geocode.longitude,
        auction_date=auction_date,
        reserve_price=reserve_price,
        org_name=parsed.contact_organisation,
        content_hash=raw_doc.content_hash,
    )

    existing_opportunities = session.execute(select(Opportunity)).scalars().all()
    best_match: Opportunity | None = None
    best_score = 0
    for candidate in existing_opportunities:
        checksums = {sl.raw_document.content_hash for sl in candidate.source_listings}
        score, _ = duplicate_score(fingerprint, candidate, checksums)
        if score > best_score:
            best_score = score
            best_match = candidate

    match_type = classify_match(best_score) if best_match else "separate"

    is_new = True
    if match_type == "merge" and best_match is not None:
        opportunity = best_match
        is_new = False
        # Fill gaps only - never overwrite a populated field with an empty one.
        if not opportunity.reserve_price and reserve_price:
            opportunity.reserve_price = reserve_price
        if not opportunity.auction_venue and parsed.auction_venue:
            opportunity.auction_venue = parsed.auction_venue
        opportunity.last_seen_at = datetime.now(UTC)
        _audit(session, "opportunity", opportunity.id, "duplicate_merged",
               f"raw_document={raw_doc.id} score={best_score}")
    else:
        prop = _build_property(parsed, normalised_address, province, geocode)
        session.add(prop)
        session.flush()

        title_bits = [b for b in [
            f"Erf {prop.erf_number}" if prop.erf_number else None,
            prop.township,
            normalised_address,
        ] if b]
        title = " - ".join(title_bits) or (raw_doc.title or "Untitled opportunity")

        opportunity = Opportunity(
            property_id=prop.id,
            opportunity_type="sheriff_sale",
            title=title,
            summary=parsed.improvements_text,
            status="needs_review" if (classification == "uncertain" or match_type == "needs_review") else "new",
            province=province,
            case_number=parsed.case_number,
            auction_date=auction_date,
            auction_time=parsed.auction_time,
            auction_venue=parsed.auction_venue,
            reserve_price=reserve_price,
            deposit_text=parsed.deposit_text,
            improvements_text=parsed.improvements_text,
            conditions_of_sale_reference=parsed.conditions_of_sale_reference,
            occupation_status="unknown",
            source_confidence="medium",
            extraction_confidence=parsed.extraction_confidence,
        )
        session.add(opportunity)
        session.flush()

        if parsed.contact_organisation or parsed.contact_email or parsed.contact_phone:
            session.add(Contact(
                opportunity_id=opportunity.id,
                contact_type="sheriff",
                organisation_name=parsed.contact_organisation,
                email=parsed.contact_email,
                phone=parsed.contact_phone,
                is_public_contact=True,
            ))

        if match_type == "needs_review" and best_match is not None:
            session.add(RiskFlag(
                opportunity_id=opportunity.id,
                code="possible_duplicate",
                title="Possible duplicate of another opportunity",
                description=f"Duplicate score {best_score}/100 against opportunity {best_match.id}. Review manually.",
                severity="medium",
            ))

        risk_specs = generate_risk_flags(
            reserve_price_present=reserve_price is not None,
            physical_address_present=bool(normalised_address),
            erf_or_sectional_present=bool(parsed.erf and (parsed.erf.erf_number or parsed.erf.sectional_unit_number or parsed.erf.portion_number)),
            case_number_present=bool(parsed.case_number),
            conditions_of_sale_reference_present=bool(parsed.conditions_of_sale_reference),
            voetstoots=parsed.voetstoots,
            sold_as_is=parsed.sold_as_is,
            auction_date=auction_date,
            auction_soon_threshold_days=settings.auction_soon_threshold_days,
            publication_date=raw_doc.publication_date,
            source_stale_threshold_days=settings.source_stale_threshold_days,
            geocode_confidence=geocode.confidence,
            mentions_inspection="inspect" in text.lower(),
        )
        for spec in risk_specs:
            session.add(RiskFlag(
                opportunity_id=opportunity.id, code=spec.code, title=spec.title,
                description=spec.description, severity=spec.severity,
            ))

        create_default_checklist(session, opportunity)
        _audit(session, "opportunity", opportunity.id, "created", f"raw_document={raw_doc.id}")

    session.add(SourceListing(
        opportunity_id=opportunity.id,
        raw_document_id=raw_doc.id,
        source_title=raw_doc.title,
        raw_extracted_json=parsed.to_dict(),
        extraction_confidence=parsed.extraction_confidence,
    ))

    erf_present = bool(parsed.erf and (parsed.erf.erf_number or parsed.erf.sectional_unit_number or parsed.erf.portion_number))
    opp_score, opp_breakdown = scoring.calculate_opportunity(
        has_market_valuation=False,
        market_discount_pct=None,
        geocode_confidence=geocode.confidence,
        province_is_target=(province or "").lower() in TARGET_PROVINCES,
        extraction_confidence=parsed.extraction_confidence,
        erf_or_sectional_present=erf_present,
        improvements_present=bool(parsed.improvements_text),
        conditions_complete=bool(parsed.conditions_of_sale_reference),
        auction_date=auction_date,
    )
    severities = [f.severity for f in opportunity.risk_flags]
    risk_score_val, risk_breakdown = scoring.calculate_risk(severities)
    completeness_val, completeness_breakdown = scoring.calculate_completeness({
        "case_number": bool(parsed.case_number),
        "auction_date": auction_date is not None,
        "auction_venue": bool(parsed.auction_venue),
        "physical_address": bool(normalised_address),
        "erf_or_sectional": erf_present,
        "reserve_price": reserve_price is not None,
        "deposit_text": bool(parsed.deposit_text),
        "contact": bool(parsed.contact_organisation or parsed.contact_email or parsed.contact_phone),
        "title_deed": bool(parsed.title_deed),
        "province": bool(province),
        "improvements_text": bool(parsed.improvements_text),
        "conditions_of_sale_reference": bool(parsed.conditions_of_sale_reference),
    })

    session.add(Score(
        opportunity_id=opportunity.id,
        scoring_version=settings.scoring_version,
        opportunity_score=opp_score,
        risk_score=risk_score_val,
        completeness_score=completeness_val,
        component_breakdown={
            "opportunity": opp_breakdown, "risk": risk_breakdown, "completeness": completeness_breakdown,
        },
    ))

    return opportunity, is_new, "processed"


def run_pipeline() -> dict:
    init_db()
    summary = {
        "documents_processed": 0, "new_opportunities": 0, "updated_opportunities": 0,
        "needs_review": 0, "duplicates_merged": 0, "rejected_no_sale": 0,
    }
    touched: list[tuple[Opportunity, bool]] = []

    with session_scope() as session:
        run, new_docs = collect_from_inbox(session)
        summary["documents_processed"] = len(new_docs)

        for raw_doc in new_docs:
            opportunity, is_new, outcome = _process_document(session, raw_doc)
            if outcome == "rejected_no_sale":
                summary["rejected_no_sale"] += 1
                continue
            if opportunity is None:
                continue
            if is_new:
                summary["new_opportunities"] += 1
            else:
                summary["updated_opportunities"] += 1
                summary["duplicates_merged"] += 1
            if opportunity.status == "needs_review":
                summary["needs_review"] += 1
            touched.append((opportunity, is_new))

        run.opportunities_created = summary["new_opportunities"]
        session.flush()

        should_send = touched and (settings.always_send_digest or any(
            (opp.latest_score().opportunity_score if opp.latest_score() else 0) >= settings.alert_min_opportunity_score
            for opp, _ in touched
        ))

        if touched:
            html, pdf_path = render_report(touched, summary)
            if should_send:
                subject = f"Property monitor: {summary['new_opportunities']} new, {summary['updated_opportunities']} updated"
                send_report_email(subject, html, pdf_path)
        else:
            print("[pipeline] No new documents in inbox this run - nothing to report.")

    return summary


if __name__ == "__main__":
    result = run_pipeline()
    print(result)
