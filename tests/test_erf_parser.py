from app.parsers.erf_parser import parse_erf


def test_simple_erf_with_township_and_extension():
    r = parse_erf("Erf 1234 Midrand Extension 5 Township")
    assert r.erf_number == "1234"
    assert r.extension == "5"
    assert "Midrand" in r.township
    assert r.confidence >= 0.7


def test_remaining_extent_of_erf():
    r = parse_erf("Remaining Extent of Erf 123 Johannesburg")
    assert r.erf_number == "123"
    assert r.remaining_extent is True


def test_portion_of_farm_number_only():
    r = parse_erf("Portion 4 of Farm 100")
    assert r.portion_number == "4"
    assert r.farm_number == "100"
    assert r.farm_name is None


def test_remaining_extent_portion_of_named_farm():
    r = parse_erf("Remaining Extent of Portion 2 of the Farm Example 456")
    assert r.portion_number == "2"
    assert r.farm_name == "Example"
    assert r.farm_number == "456"
    assert r.remaining_extent is True


def test_sectional_title_unit_and_scheme():
    r = parse_erf("Unit 12 of Sectional Title Scheme SS123/2009")
    assert r.sectional_unit_number == "12"
    assert r.sectional_title_scheme == "SS123/2009"


def test_sectional_plan_section_number():
    r = parse_erf("Section No. 8 as shown on Sectional Plan SS45/2018")
    assert r.sectional_unit_number == "8"
    assert r.sectional_title_scheme == "SS45/2018"


def test_holding():
    r = parse_erf("Holding 10 Agricultural Holdings")
    assert r.erf_number == "10"
    assert "Holdings" in r.township


def test_section_only_common_property_phrasing():
    r = parse_erf("A unit consisting of section 4 and an undivided share in common property")
    assert r.sectional_unit_number == "4"


def test_no_property_description_yields_zero_confidence():
    r = parse_erf("This document contains no property description at all.")
    assert r.confidence == 0.0
    assert r.erf_number is None
