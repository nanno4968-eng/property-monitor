from datetime import UTC, datetime, timedelta

from app.services import scoring


def test_missing_market_valuation_scores_zero_not_neutral():
    score, breakdown = scoring.calculate_opportunity(
        has_market_valuation=False,
        market_discount_pct=None,
        geocode_confidence=None,
        province_is_target=True,
        extraction_confidence=1.0,
        erf_or_sectional_present=True,
        improvements_present=True,
        conditions_complete=True,
        auction_date=datetime.now(UTC) + timedelta(days=30),
    )
    assert breakdown["components"]["discount_to_market_estimate"] == 0.0
    assert breakdown["components"]["rental_potential"] == 0.0
    # Occupation is never confirmed by a notice alone.
    assert breakdown["components"]["occupation_clarity"] == 0.0


def test_full_extraction_confidence_maxes_source_reliability_component():
    score, breakdown = scoring.calculate_opportunity(
        has_market_valuation=False, market_discount_pct=None,
        geocode_confidence="high", province_is_target=True,
        extraction_confidence=1.0, erf_or_sectional_present=True,
        improvements_present=True, conditions_complete=True,
        auction_date=None,
    )
    assert breakdown["components"]["source_reliability"] == 10.0


def test_out_of_range_extraction_confidence_is_clamped():
    # Regression test: a caller-side bug once let extraction_confidence
    # exceed 1.0 (e.g. 1.17), which silently pushed this component past its
    # stated 10-point max. The scoring function must defend against that.
    score, breakdown = scoring.calculate_opportunity(
        has_market_valuation=False, market_discount_pct=None,
        geocode_confidence="high", province_is_target=True,
        extraction_confidence=1.17, erf_or_sectional_present=True,
        improvements_present=True, conditions_complete=True,
        auction_date=None,
    )
    assert breakdown["components"]["source_reliability"] == 10.0


def test_opportunity_score_never_exceeds_100_components_sum():
    score, breakdown = scoring.calculate_opportunity(
        has_market_valuation=True, market_discount_pct=100.0,
        geocode_confidence="high", province_is_target=True,
        extraction_confidence=1.0, erf_or_sectional_present=True,
        improvements_present=True, conditions_complete=True,
        auction_date=datetime.now(UTC) + timedelta(days=60),
    )
    assert score <= 100


def test_risk_score_accumulates_severity_weights_and_caps_at_100():
    score, breakdown = scoring.calculate_risk(["critical", "high", "high", "medium", "low"])
    assert score == 25 + 15 + 15 + 8 + 3
    score_capped, _ = scoring.calculate_risk(["critical"] * 10)
    assert score_capped == 100.0


def test_risk_score_zero_when_no_flags():
    score, _ = scoring.calculate_risk([])
    assert score == 0.0


def test_completeness_score_rewards_weighted_fields():
    score, breakdown = scoring.calculate_completeness({
        "case_number": True, "auction_date": True, "auction_venue": True,
        "physical_address": True, "erf_or_sectional": True, "reserve_price": True,
        "deposit_text": True, "contact": True, "title_deed": True, "province": True,
        "improvements_text": True, "conditions_of_sale_reference": True,
    })
    assert score == 100.0


def test_completeness_score_zero_when_nothing_present():
    score, _ = scoring.calculate_completeness({})
    assert score == 0.0
