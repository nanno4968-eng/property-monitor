from datetime import UTC, datetime
from decimal import Decimal

from app.models import Contact, Opportunity, Property
from app.services.dedup import CandidateFingerprint, classify_match, duplicate_score


def _existing_opportunity(**overrides) -> Opportunity:
    prop = Property(
        erf_number="1234",
        township="Midrand Extension 5",
        canonical_address="10 Example Street, Midrand, Gauteng",
        latitude=-25.99, longitude=28.13,
    )
    opp = Opportunity(
        property_id="placeholder",
        opportunity_type="sheriff_sale",
        title="Erf 1234 Midrand Extension 5",
        case_number="12345/2026",
        auction_date=datetime(2026, 8, 18, tzinfo=UTC),
        reserve_price=Decimal("850000.00"),
    )
    opp.property_ = prop
    opp.contacts = [Contact(opportunity_id="placeholder", contact_type="sheriff", organisation_name="Sheriff of Johannesburg North")]
    opp.source_listings = []
    for k, v in overrides.items():
        setattr(opp, k, v)
    return opp


def test_same_document_checksum_is_automatic_duplicate():
    existing = _existing_opportunity()
    new = CandidateFingerprint(content_hash="abc123")
    score, breakdown = duplicate_score(new, existing, existing_checksums={"abc123"})
    assert score == 100
    assert classify_match(score) == "merge"


def test_exact_case_number_alone_is_not_enough_to_merge():
    existing = _existing_opportunity()
    new = CandidateFingerprint(case_number="12345/2026")
    score, breakdown = duplicate_score(new, existing, existing_checksums=set())
    assert breakdown["exact_case_number"] == 30
    assert score == 30
    assert classify_match(score) == "separate"


def test_erf_and_township_plus_case_number_crosses_review_threshold():
    existing = _existing_opportunity()
    new = CandidateFingerprint(case_number="12345/2026", erf_number="1234", township="Midrand Extension 5")
    score, _ = duplicate_score(new, existing, existing_checksums=set())
    assert score == 65  # 30 + 35
    assert classify_match(score) == "needs_review"


def test_multiple_strong_signals_trigger_automatic_merge():
    existing = _existing_opportunity()
    new = CandidateFingerprint(
        case_number="12345/2026",
        erf_number="1234",
        township="Midrand Extension 5",
        auction_date=datetime(2026, 8, 18, tzinfo=UTC),
        reserve_price=Decimal("850000.00"),
        org_name="Sheriff of Johannesburg North",
    )
    score, breakdown = duplicate_score(new, existing, existing_checksums=set())
    # 30 (case) + 35 (erf+township) + 10 (auction date) + 5 (reserve) + 5 (org) = 85
    assert score == 85
    assert classify_match(score) == "merge"


def test_coordinates_within_50m_awards_points():
    existing = _existing_opportunity()
    new = CandidateFingerprint(latitude=-25.9901, longitude=28.1301)  # a few metres away
    score, breakdown = duplicate_score(new, existing, existing_checksums=set())
    assert breakdown.get("coordinates_within_50m") == 15


def test_unrelated_property_scores_low():
    existing = _existing_opportunity()
    new = CandidateFingerprint(
        case_number="99999/2099",
        erf_number="9999",
        township="Somewhere Else",
    )
    score, _ = duplicate_score(new, existing, existing_checksums=set())
    assert score == 0
    assert classify_match(score) == "separate"
