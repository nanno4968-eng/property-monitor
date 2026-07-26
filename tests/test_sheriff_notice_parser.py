from pathlib import Path

from app.parsers.sheriff_notice_parser import parse_sheriff_notice

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "sample_sheriff_notice.txt"


def test_sample_notice_matches_brief_expected_output():
    text = SAMPLE_PATH.read_text()
    r = parse_sheriff_notice(text)

    assert r.case_number == "12345/2026"
    assert r.sheriff_name == "Sheriff of Johannesburg North"
    assert r.auction_date_raw == "18 August 2026"
    assert r.auction_time == "10:00"
    assert "Example Road" in r.auction_venue
    assert "Johannesburg" in r.auction_venue
    assert r.physical_address == "10 Example Street, Midrand, Gauteng"
    assert r.erf.erf_number == "1234"
    assert r.erf.township == "Midrand Extension 5"
    assert r.title_deed == "T12345/2015"
    assert r.land_area_m2 == 1000.0
    assert r.reserve_price_raw == "R850,000"
    assert r.province == "Gauteng"
    assert r.bedrooms == 3
    assert r.bathrooms == 2
    assert r.contact_email == "auctions@example.org"
    assert r.contact_phone == "010 000 0000"
    assert r.voetstoots is False
    assert r.extraction_confidence >= 0.8


def test_missing_reserve_price_lowers_confidence_not_favourable():
    text = SAMPLE_PATH.read_text().replace("Reserve price:\nR850,000", "")
    r = parse_sheriff_notice(text)
    assert r.reserve_price_raw is None
    assert r.extraction_confidence < 1.0


def test_empty_text_returns_no_fields():
    r = parse_sheriff_notice("")
    assert r.case_number is None
    assert r.extraction_confidence == 0.0
