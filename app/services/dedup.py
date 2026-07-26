"""Deduplication service (brief section 11).

Never deletes source listings when merging - every source record is kept
under the canonical opportunity (see pipeline.py for how this is applied).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from rapidfuzz import fuzz

from app.models import Opportunity

MERGE_THRESHOLD = 85
REVIEW_THRESHOLD = 65


@dataclass
class CandidateFingerprint:
    case_number: str | None = None
    erf_number: str | None = None
    township: str | None = None
    sectional_unit_number: str | None = None
    sectional_title_scheme: str | None = None
    normalised_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    auction_date: datetime | None = None
    reserve_price: Decimal | None = None
    org_name: str | None = None
    content_hash: str | None = None


def _haversine_metres(lat1, lon1, lat2, lon2) -> float:
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def duplicate_score(new: CandidateFingerprint, existing: Opportunity, existing_checksums: set[str]) -> tuple[int, dict]:
    """Returns (score 0-100, breakdown dict) comparing a new candidate against
    an existing Opportunity + its property + source listings."""
    breakdown: dict[str, int] = {}
    prop = existing.property_

    if new.content_hash and new.content_hash in existing_checksums:
        return 100, {"same_source_document_checksum": 100}

    if new.case_number and existing.case_number and new.case_number.strip().lower() == existing.case_number.strip().lower():
        breakdown["exact_case_number"] = 30

    if (
        new.erf_number and prop and prop.erf_number
        and new.erf_number.strip().lower() == prop.erf_number.strip().lower()
        and new.township and prop.township
        and new.township.strip().lower() == prop.township.strip().lower()
    ):
        breakdown["exact_erf_and_township"] = 35

    if (
        new.sectional_unit_number and prop and prop.sectional_unit_number
        and new.sectional_unit_number == prop.sectional_unit_number
        and new.sectional_title_scheme and prop.sectional_title_scheme
        and new.sectional_title_scheme.replace(" ", "").lower() == prop.sectional_title_scheme.replace(" ", "").lower()
    ):
        breakdown["exact_sectional_unit_and_scheme"] = 35

    if new.normalised_address and prop and prop.canonical_address:
        similarity = fuzz.ratio(new.normalised_address.lower(), prop.canonical_address.lower())
        if similarity >= 95:
            breakdown["exact_normalised_address"] = 30

    if (
        new.latitude is not None and new.longitude is not None
        and prop and prop.latitude is not None and prop.longitude is not None
    ):
        distance = _haversine_metres(new.latitude, new.longitude, prop.latitude, prop.longitude)
        if distance <= 50:
            breakdown["coordinates_within_50m"] = 15

    if new.auction_date and existing.auction_date and new.auction_date.date() == existing.auction_date.date():
        breakdown["same_auction_date"] = 10

    if new.reserve_price is not None and existing.reserve_price is not None and new.reserve_price == existing.reserve_price:
        breakdown["same_reserve_price"] = 5

    if new.org_name:
        existing_orgs = {c.organisation_name.lower() for c in existing.contacts if c.organisation_name}
        if new.org_name.lower() in existing_orgs:
            breakdown["same_sheriff_or_auctioneer"] = 5

    return sum(breakdown.values()), breakdown


def classify_match(score: int) -> str:
    if score >= MERGE_THRESHOLD:
        return "merge"
    if score >= REVIEW_THRESHOLD:
        return "needs_review"
    return "separate"
