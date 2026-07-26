"""Scoring engine (brief section 13).

Three separate 0-100 scores are produced - opportunity, risk, completeness -
and are never combined into one misleading number. Every component is
explained in the breakdown that gets stored alongside the Score row.

Conservative-by-design: anything the parser could not determine scores as
unfavourable (0 for opportunity components, elevated for risk), never as a
neutral middle value. A genuine market-value discount component needs a
manual valuation input (brief section 14) that doesn't exist yet in this
pipeline-only edition, so it is explicitly reported as unavailable rather
than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

SCORING_VERSION_NOTE = (
    "Automated component only - discount-to-market-value and rental-potential "
    "components require a manual valuation input not yet collected by this "
    "pipeline, so they score 0 until a human supplies one. Treat the opportunity "
    "score as a screening signal, not a valuation."
)


@dataclass
class ScoreResult:
    opportunity_score: float
    risk_score: float
    completeness_score: float
    breakdown: dict


_RISK_SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 8, "low": 3}

_COMPLETENESS_FIELDS = {
    # field_name: (present: bool, weight)
}


def calculate_completeness(fields_present: dict[str, bool]) -> tuple[float, dict]:
    """fields_present maps field name -> bool, already weighted by the caller
    supplying only the fields that matter for a sheriff-sale opportunity."""
    weights = {
        "case_number": 2, "auction_date": 2, "auction_venue": 1, "physical_address": 2,
        "erf_or_sectional": 2, "reserve_price": 2, "deposit_text": 1, "contact": 1,
        "title_deed": 1, "province": 1, "improvements_text": 1,
        "conditions_of_sale_reference": 1,
    }
    total_weight = sum(weights.values())
    earned = sum(w for f, w in weights.items() if fields_present.get(f))
    score = round(100 * earned / total_weight, 1)
    return score, {"weights": weights, "present": fields_present}


def calculate_risk(risk_flags_severities: list[str]) -> tuple[float, dict]:
    total = sum(_RISK_SEVERITY_WEIGHTS.get(sev, 5) for sev in risk_flags_severities)
    score = min(100.0, float(total))
    counts = {sev: risk_flags_severities.count(sev) for sev in set(risk_flags_severities)}
    return score, {"severity_counts": counts, "severity_weights": _RISK_SEVERITY_WEIGHTS}


def calculate_opportunity(
    *,
    has_market_valuation: bool,
    market_discount_pct: float | None,
    geocode_confidence: str | None,
    province_is_target: bool,
    extraction_confidence: float,
    erf_or_sectional_present: bool,
    improvements_present: bool,
    conditions_complete: bool,
    auction_date: datetime | None,
) -> tuple[float, dict]:
    components: dict[str, float] = {}

    # 25 pts: discount to conservative market estimate - unavailable in MVP.
    if has_market_valuation and market_discount_pct is not None:
        components["discount_to_market_estimate"] = round(min(25.0, max(0.0, market_discount_pct * 25 / 100)), 1)
    else:
        components["discount_to_market_estimate"] = 0.0  # unknown -> unfavourable, not neutral

    # 15 pts: location and demand - crude proxy from geocode confidence + target province.
    if geocode_confidence == "high" and province_is_target:
        components["location_and_demand"] = 15.0
    elif province_is_target:
        components["location_and_demand"] = 7.0
    else:
        components["location_and_demand"] = 0.0

    # 10 pts: rental potential - unavailable without a valuation/rental feed.
    components["rental_potential"] = 0.0

    # 10 pts: source reliability, scaled from parser extraction confidence.
    components["source_reliability"] = round(extraction_confidence * 10, 1)

    # 10 pts: property description clarity.
    components["property_description_clarity"] = (
        10.0 if (erf_or_sectional_present and improvements_present)
        else 5.0 if (erf_or_sectional_present or improvements_present)
        else 0.0
    )

    # 10 pts: occupation clarity - always 0; occupation is never confirmed by a notice alone.
    components["occupation_clarity"] = 0.0

    # 10 pts: repair-risk estimate - only partial credit for having *some* description.
    components["repair_risk_estimate"] = 3.0 if improvements_present else 0.0

    # 5 pts: time available for due diligence.
    if auction_date:
        days = (auction_date - datetime.now(UTC)).days
        components["time_available_for_due_diligence"] = round(min(5.0, max(0.0, days / 6)), 1)
    else:
        components["time_available_for_due_diligence"] = 0.0

    # 5 pts: sale-condition completeness.
    components["sale_condition_completeness"] = 5.0 if conditions_complete else 0.0

    total = round(sum(components.values()), 1)
    return total, {"components": components, "note": SCORING_VERSION_NOTE}
