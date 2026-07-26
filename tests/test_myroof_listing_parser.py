from app.parsers.myroof_listing_parser import parse_myroof_listing

# Plain-text approximation of what BeautifulSoup .get_text() returns for a
# real MyRoof bank-listing detail page (verified against
# https://www.myroof.co.za/MR676778-... during development).
BANK_LISTING_FIXTURE = """
Standard Bank EasySell 3 Bedroom House for Sale in Fochville - MR676778
Fochville
R 1,100,000
House in Fochville - MR676778
R 1,100,000
Transaction in Progress for R 950,000
3
bed
2
bath
1
garage
Property Key Features
Rooms
3 Bedrooms
2 Bathrooms
2 Living Rooms
Flatlet
Kitchen
1 Kitchen
Parking
1 Car Port
1 Garage
More Features
Property Type - House
Seller Type - Standard Bank EasySell
"""

PRIVATE_LISTING_FIXTURE = """
3 Bedroom House for Sale in Fochville - MR540015
This house is a spacious dream comes true!!
R 1,590,000
3 Bedrooms
2 Bathrooms
Property Type - House
"""


def test_bank_listing_extracts_all_key_fields():
    r = parse_myroof_listing(BANK_LISTING_FIXTURE, mr_code="MR676778")
    assert r.is_bank_listing is True
    assert r.seller_type == "Standard Bank EasySell"
    assert r.opportunity_type == "assisted_sale"
    assert r.property_type == "House"
    assert r.asking_price_raw == "R1,100,000"
    assert r.transaction_price_raw == "R950,000"
    assert r.bedrooms == 3
    assert r.bathrooms == 2
    assert r.garages == 2  # 1 car port + 1 garage


def test_price_extraction_does_not_pick_up_the_mr_code():
    # Regression test: the naive regex used to match "676778" out of
    # "MR676778" and report it as a price.
    r = parse_myroof_listing(BANK_LISTING_FIXTURE, mr_code="MR676778")
    assert r.asking_price_raw != "R676778"


def test_private_listing_is_not_treated_as_a_bank_listing():
    r = parse_myroof_listing(PRIVATE_LISTING_FIXTURE, mr_code="MR540015")
    assert r.is_bank_listing is False
    assert r.seller_type is None


def test_empty_text_is_not_a_bank_listing():
    r = parse_myroof_listing("", mr_code="MR000000")
    assert r.is_bank_listing is False
    assert r.bedrooms is None


def test_seller_type_classification_covers_all_known_programs():
    cases = {
        "Standard Bank Repossessed": "bank_repossession",
        "Standard Bank Pre-Hammer": "urgent_sale",
        "Standard Bank Sheriff Auctions": "urgent_sale",
        "Standard Bank Insolvent": "insolvent_estate",
        "FNB Quick Sell": "assisted_sale",
        "FNB Repossessed": "bank_repossession",
        "FNB Bank Owned": "bank_repossession",
        "Nedbank Repossessed": "bank_repossession",
        "SA Home Loans Sell Assist": "assisted_sale",
    }
    for seller_type, expected in cases.items():
        text = f"Seller Type - {seller_type}\nR 1,000,000\n2 Bedrooms\n1 Bathrooms\n"
        r = parse_myroof_listing(text, mr_code="MRTEST")
        assert r.opportunity_type == expected, f"{seller_type} -> {r.opportunity_type}, expected {expected}"
