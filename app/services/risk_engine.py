"""Risk flag engine (brief section 12).

Implements the subset of flags that can be determined deterministically from
a parsed sheriff-sale notice. Every flag here is conservative: uncertainty
raises risk, it never lowers it (brief section 13 scoring rules).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class RiskFlagSpec:
    code: str
    title: str
    description: str
    severity: str  # low, medium, high, critical


def generate_risk_flags(
    *,
    reserve_price_present: bool,
    physical_address_present: bool,
    erf_or_sectional_present: bool,
    case_number_present: bool,
    conditions_of_sale_reference_present: bool,
    voetstoots: bool,
    sold_as_is: bool,
    auction_date: datetime | None,
    auction_soon_threshold_days: int,
    publication_date: datetime | None,
    source_stale_threshold_days: int,
    geocode_confidence: str | None,
    mentions_inspection: bool,
) -> list[RiskFlagSpec]:
    flags: list[RiskFlagSpec] = []
    now = datetime.now(UTC)

    # Occupation is never confirmed by a notice alone - always flag until a
    # human due-diligence step confirms otherwise.
    flags.append(RiskFlagSpec(
        code="occupation_status_unknown",
        title="Occupation status unknown",
        description="The notice does not confirm whether the property is vacant or occupied. "
                     "Vacant possession is never guaranteed by a sheriff sale.",
        severity="high",
    ))

    if not mentions_inspection:
        flags.append(RiskFlagSpec(
            code="no_internal_inspection",
            title="No internal inspection mentioned",
            description="No inspection arrangement was found in the notice text.",
            severity="medium",
        ))

    if voetstoots:
        flags.append(RiskFlagSpec(
            code="sold_voetstoots",
            title="Sold voetstoots",
            description="The property is sold voetstoots (as-is, with all faults, no warranties).",
            severity="medium",
        ))
    elif sold_as_is:
        flags.append(RiskFlagSpec(
            code="sold_as_is",
            title="Sold as-is",
            description="The notice indicates the property is sold as-is.",
            severity="medium",
        ))

    if not reserve_price_present:
        flags.append(RiskFlagSpec(
            code="reserve_price_absent",
            title="Reserve price absent",
            description="No reserve price was extracted from the notice; the sale may proceed "
                         "without a stated reserve.",
            severity="high",
        ))

    if auction_date:
        days_until = (auction_date - now).days
        if 0 <= days_until < auction_soon_threshold_days:
            flags.append(RiskFlagSpec(
                code="auction_date_less_than_threshold",
                title=f"Auction date less than {auction_soon_threshold_days} days away",
                description=f"Only {days_until} day(s) remain for due diligence before the auction.",
                severity="high",
            ))
        elif days_until < 0:
            flags.append(RiskFlagSpec(
                code="auction_status_not_recently_confirmed",
                title="Auction date has passed",
                description="The extracted auction date is in the past; confirm whether the sale "
                             "proceeded, was postponed, or was cancelled before treating this as active.",
                severity="critical",
            ))

    if not physical_address_present:
        flags.append(RiskFlagSpec(
            code="address_incomplete",
            title="Address incomplete",
            description="No physical address was extracted from the notice.",
            severity="medium",
        ))

    if not erf_or_sectional_present:
        flags.append(RiskFlagSpec(
            code="erf_description_incomplete",
            title="Erf/deeds description incomplete",
            description="No erf, portion, farm, or sectional-title description was extracted.",
            severity="medium",
        ))

    if not case_number_present:
        flags.append(RiskFlagSpec(
            code="legal_reference_missing",
            title="Legal case reference missing",
            description="No case number was extracted; this makes independent verification harder.",
            severity="medium",
        ))

    if not conditions_of_sale_reference_present:
        flags.append(RiskFlagSpec(
            code="conditions_of_sale_missing",
            title="Conditions of sale document not referenced",
            description="The notice does not reference a conditions-of-sale document.",
            severity="medium",
        ))

    if publication_date:
        age_days = (now - publication_date).days
        if age_days > source_stale_threshold_days:
            flags.append(RiskFlagSpec(
                code="source_older_than_threshold",
                title="Source document may be stale",
                description=f"This source document is {age_days} days old; re-confirm the sale is "
                             f"still active before relying on it.",
                severity="medium",
            ))

    if geocode_confidence in (None, "low"):
        flags.append(RiskFlagSpec(
            code="geocode_confidence_low",
            title="Geocode confidence low or unavailable",
            description="The mapped location, if any, should be treated as approximate.",
            severity="low",
        ))

    # Standing flag until a human clears it - core principle 3 (human verification).
    flags.append(RiskFlagSpec(
        code="title_or_deeds_verification_outstanding",
        title="Title/deeds verification outstanding",
        description="Registered ownership, bonds, and title have not been independently verified "
                     "against the Deeds Office. Required before this lead can be marked verified.",
        severity="medium",
    ))

    return flags
