from datetime import UTC, datetime, timedelta

from app.services.risk_engine import generate_risk_flags


def _base_kwargs(**overrides):
    kwargs = dict(
        reserve_price_present=True,
        physical_address_present=True,
        erf_or_sectional_present=True,
        case_number_present=True,
        conditions_of_sale_reference_present=True,
        voetstoots=False,
        sold_as_is=False,
        auction_date=datetime.now(UTC) + timedelta(days=30),
        auction_soon_threshold_days=7,
        publication_date=None,
        source_stale_threshold_days=30,
        geocode_confidence="high",
        mentions_inspection=True,
    )
    kwargs.update(overrides)
    return kwargs


def test_occupation_and_title_verification_flags_always_present():
    flags = generate_risk_flags(**_base_kwargs())
    codes = {f.code for f in flags}
    assert "occupation_status_unknown" in codes
    assert "title_or_deeds_verification_outstanding" in codes


def test_missing_reserve_price_flagged_high():
    flags = generate_risk_flags(**_base_kwargs(reserve_price_present=False))
    match = [f for f in flags if f.code == "reserve_price_absent"]
    assert match and match[0].severity == "high"


def test_auction_soon_flagged():
    flags = generate_risk_flags(**_base_kwargs(auction_date=datetime.now(UTC) + timedelta(days=2)))
    codes = {f.code for f in flags}
    assert "auction_date_less_than_threshold" in codes


def test_past_auction_date_flagged_critical():
    flags = generate_risk_flags(**_base_kwargs(auction_date=datetime.now(UTC) - timedelta(days=5)))
    match = [f for f in flags if f.code == "auction_status_not_recently_confirmed"]
    assert match and match[0].severity == "critical"


def test_voetstoots_flagged():
    flags = generate_risk_flags(**_base_kwargs(voetstoots=True))
    codes = {f.code for f in flags}
    assert "sold_voetstoots" in codes
    assert "sold_as_is" not in codes  # voetstoots takes precedence, not double-flagged


def test_incomplete_fields_each_flagged():
    flags = generate_risk_flags(**_base_kwargs(
        physical_address_present=False,
        erf_or_sectional_present=False,
        case_number_present=False,
        conditions_of_sale_reference_present=False,
    ))
    codes = {f.code for f in flags}
    assert {"address_incomplete", "erf_description_incomplete", "legal_reference_missing",
            "conditions_of_sale_missing"} <= codes


def test_stale_source_flagged():
    flags = generate_risk_flags(**_base_kwargs(
        publication_date=datetime.now(UTC) - timedelta(days=60),
    ))
    codes = {f.code for f in flags}
    assert "source_older_than_threshold" in codes


def test_complete_recent_notice_has_minimum_standing_flags_only():
    flags = generate_risk_flags(**_base_kwargs())
    codes = {f.code for f in flags}
    # Occupation and title verification are always present; nothing else should fire
    # when every other field is complete and the auction is comfortably in the future.
    assert codes == {"occupation_status_unknown", "title_or_deeds_verification_outstanding"}
