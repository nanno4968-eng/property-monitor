"""Deterministic parser for MyRoof.co.za bank-program listing detail pages.

MyRoof (myroof.co.za) hosts the banks' own official repossessed/distressed
property listings (Standard Bank, FNB, Nedbank, SA Home Loans). Verified
before building this: robots.txt disallows only /templates/, there's no
login wall, no "do not reproduce" notice, and the site publishes a sitemap
specifically so it gets crawled - see docs/source_policy.md for the full
reasoning.

Each listing detail page states its program cleanly in a "Seller Type - X"
line, which is the anchor this parser relies on - deliberately not scraping
based on fragile page layout/CSS, just the literal labelled fields.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SELLER_TYPE_RE = re.compile(r"Seller\s*Type\s*-\s*(?P<seller_type>[^\n]+)", re.IGNORECASE)
_PROPERTY_TYPE_RE = re.compile(r"Property\s*Type\s*-\s*(?P<property_type>[^\n]+)", re.IGNORECASE)
_TRANSACTION_PRICE_RE = re.compile(
    r"Transaction\s+in\s+Progress\s+for\s+R\s?(?P<price>[\d,]+)", re.IGNORECASE
)
_ASKING_PRICE_RE = re.compile(r"(?<![A-Za-z])R\s?(?P<price>[\d,]{4,})")
_BEDROOMS_RE = re.compile(r"(?P<num>\d+)\s*Bedrooms?\b", re.IGNORECASE)
_BATHROOMS_RE = re.compile(r"(?P<num>\d+)\s*Bathrooms?\b", re.IGNORECASE)
_GARAGE_RE = re.compile(r"(?P<num>\d+)\s*Garage[s]?\b", re.IGNORECASE)
_CARPORT_RE = re.compile(r"(?P<num>\d+)\s*Car\s*Port[s]?\b", re.IGNORECASE)
_ERF_SIZE_RE = re.compile(r"(?P<size>[\d,]+)\s*m2\s*erf", re.IGNORECASE)
_FLOOR_SIZE_RE = re.compile(r"(?P<size>[\d,]+)\s*m2\s*floor", re.IGNORECASE)

# Maps a "Seller Type" string to the brief's opportunity_type vocabulary.
_SELLER_TYPE_TO_OPPORTUNITY_TYPE = (
    (r"repossess|bank\s*owned", "bank_repossession"),
    (r"easysell|quick\s*sell|sell\s*assist", "assisted_sale"),
    (r"pre-?hammer|sheriff", "urgent_sale"),
    (r"insolvent", "insolvent_estate"),
)


@dataclass
class MyRoofListingResult:
    mr_code: str | None = None
    seller_type: str | None = None
    opportunity_type: str = "assisted_sale"
    property_type: str | None = None
    asking_price_raw: str | None = None
    transaction_price_raw: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    garages: int | None = None
    erf_size_m2: float | None = None
    floor_size_m2: float | None = None
    is_bank_listing: bool = False
    fields_found: list[str] = None

    def __post_init__(self):
        if self.fields_found is None:
            self.fields_found = []

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "fields_found"}


def _classify_opportunity_type(seller_type: str) -> str:
    for pattern, opp_type in _SELLER_TYPE_TO_OPPORTUNITY_TYPE:
        if re.search(pattern, seller_type, re.IGNORECASE):
            return opp_type
    return "assisted_sale"


def parse_myroof_listing(page_text: str, mr_code: str | None = None) -> MyRoofListingResult:
    """Parse a MyRoof listing detail page's visible text into structured fields.

    Only listings with a recognisable "Seller Type" (a bank program) are
    treated as genuine distressed-sale opportunities - ordinary private
    listings on the same site are explicitly out of scope for this tool and
    should be filtered out by the collector before this is even called, but
    `is_bank_listing` is set here too as a defensive second check.
    """
    result = MyRoofListingResult(mr_code=mr_code)

    m = _SELLER_TYPE_RE.search(page_text)
    if m:
        result.seller_type = m.group("seller_type").strip()
        result.opportunity_type = _classify_opportunity_type(result.seller_type)
        result.is_bank_listing = True
        result.fields_found.append("seller_type")

    m = _PROPERTY_TYPE_RE.search(page_text)
    if m:
        result.property_type = m.group("property_type").strip()
        result.fields_found.append("property_type")

    m = _TRANSACTION_PRICE_RE.search(page_text)
    if m:
        result.transaction_price_raw = "R" + m.group("price")
        result.fields_found.append("transaction_price")

    # Take the first plausible asking price mentioned (appears near the top,
    # before "Transaction in Progress" if that's present).
    m = _ASKING_PRICE_RE.search(page_text)
    if m:
        result.asking_price_raw = "R" + m.group("price")
        result.fields_found.append("asking_price")

    m = _BEDROOMS_RE.search(page_text)
    if m:
        result.bedrooms = int(m.group("num"))
        result.fields_found.append("bedrooms")

    m = _BATHROOMS_RE.search(page_text)
    if m:
        result.bathrooms = int(m.group("num"))
        result.fields_found.append("bathrooms")

    garages = 0
    m = _GARAGE_RE.search(page_text)
    if m:
        garages += int(m.group("num"))
    m = _CARPORT_RE.search(page_text)
    if m:
        garages += int(m.group("num"))
    if garages:
        result.garages = garages
        result.fields_found.append("garages")

    m = _ERF_SIZE_RE.search(page_text)
    if m:
        result.erf_size_m2 = float(m.group("size").replace(",", ""))

    m = _FLOOR_SIZE_RE.search(page_text)
    if m:
        result.floor_size_m2 = float(m.group("size").replace(",", ""))

    return result
