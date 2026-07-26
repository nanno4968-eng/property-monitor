"""Deterministic parser for South African "Notice of Sale in Execution"
(sheriff-sale) documents - brief sections 22-23.

Regex-first extraction with a per-field confidence score. Nothing here calls
an external AI API; that stays an optional future extension behind an
interface, per the brief's coding standards ("deterministic parsing before AI
extraction").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field

from app.parsers.erf_parser import parse_erf
from app.parsers.text_cleaning import clean_whitespace

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_CASE_NO_RE = re.compile(r"CASE\s*NO\.?:?\s*(?P<case>[A-Z0-9/\-]+)", re.IGNORECASE)

_SHERIFF_AUCTION_RE = re.compile(
    r"SHERIFF\s+OF\s+(?P<sheriff>[A-Z][A-Za-z\s]*?)\s+on\s+"
    r"(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+at\s+(?P<time>\d{1,2}[:h]\d{2})"
    r"\s+at\s+(?P<venue>.+?):",
    re.IGNORECASE | re.DOTALL,
)

_PHYSICAL_ADDRESS_RE = re.compile(
    r"Physical\s+address:?\s*\n?(?P<address>[^\n]+)", re.IGNORECASE
)

_IMPROVEMENTS_RE = re.compile(
    r"Improvements:?\s*\n?(?P<improvements>[^\n]+(?:\n(?!Reserve|Contact|Deposit)[^\n]+)*)",
    re.IGNORECASE,
)

_RESERVE_PRICE_RE = re.compile(
    r"Reserve\s+price:?\s*\n?R\s?(?P<price>[\d,\s]+(?:\.\d{2})?)", re.IGNORECASE
)

_DEPOSIT_RE = re.compile(
    r"Deposit:?\s*\n?(?P<deposit>[^\n]+)", re.IGNORECASE
)

_CONTACT_BLOCK_RE = re.compile(
    r"Contact:?\s*\n?(?P<block>(?:[^\n]+\n?){1,6})", re.IGNORECASE
)

_EMAIL_RE = re.compile(r"[\w.\-]+@[\w\-]+\.[A-Za-z.]+")
_PHONE_RE = re.compile(r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{4}\b")

_TITLE_DEED_RE = re.compile(r"DEED OF TRANSFER\s+(?P<deed>T\d+/\d{4})", re.IGNORECASE)
_REGISTRATION_DIVISION_RE = re.compile(r"REGISTRATION\s+DIVISION\s+(?P<div>[A-Z]{1,3}\.?[A-Z]?\.?)", re.IGNORECASE)
_PROVINCE_RE = re.compile(r"PROVINCE\s+OF\s+(?P<province>[A-Z][A-Za-z\s]+?)(?:\n|$|,)", re.IGNORECASE)
_LAND_AREA_RE = re.compile(r"MEASURING\s+(?P<area>[\d\s,]+)\s*SQUARE\s+METRES", re.IGNORECASE)
_BEDROOMS_RE = re.compile(
    r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+bedrooms?", re.IGNORECASE
)
_BATHROOMS_RE = re.compile(
    r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+bathrooms?", re.IGNORECASE
)
_VOETSTOOTS_RE = re.compile(r"voetstoots", re.IGNORECASE)
_AS_IS_RE = re.compile(r"\bas[\s-]is\b", re.IGNORECASE)
_CONDITIONS_REF_RE = re.compile(
    r"conditions\s+of\s+sale[^\n]{0,80}?(?P<ref>[A-Z0-9/\-]{3,})", re.IGNORECASE
)


def _word_or_digit_to_int(raw: str) -> int | None:
    raw = raw.strip().lower()
    if raw.isdigit():
        return int(raw)
    return _WORD_NUMBERS.get(raw)


@dataclass
class SheriffNoticeParseResult:
    case_number: str | None = None
    sheriff_name: str | None = None
    auction_date_raw: str | None = None
    auction_time: str | None = None
    auction_venue: str | None = None
    physical_address: str | None = None
    improvements_text: str | None = None
    reserve_price_raw: str | None = None
    deposit_text: str | None = None
    contact_organisation: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    title_deed: str | None = None
    registration_division: str | None = None
    province: str | None = None
    land_area_m2: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    voetstoots: bool = False
    sold_as_is: bool = False
    conditions_of_sale_reference: str | None = None
    erf: object = None  # ErfParseResult, kept loosely typed to avoid import cycles
    fields_found: list[str] = dc_field(default_factory=list)
    extraction_confidence: float = 0.0

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k not in ("erf", "fields_found")}
        d["erf"] = self.erf.to_dict() if self.erf else None
        return d


# Fields that materially matter for downstream scoring/risk - used to weight confidence.
_KEY_FIELDS = (
    "case_number", "sheriff_name", "auction_date_raw", "physical_address",
    "reserve_price_raw", "erf_number",
)


def parse_sheriff_notice(raw_text: str) -> SheriffNoticeParseResult:
    text = clean_whitespace(raw_text)
    result = SheriffNoticeParseResult()

    m = _CASE_NO_RE.search(text)
    if m:
        result.case_number = m.group("case").strip()
        result.fields_found.append("case_number")

    m = _SHERIFF_AUCTION_RE.search(text)
    if m:
        result.sheriff_name = f"Sheriff of {m.group('sheriff').strip()}"
        result.auction_date_raw = m.group("date").strip()
        result.auction_time = m.group("time").strip().replace("h", ":")
        result.auction_venue = " ".join(m.group("venue").split())
        result.fields_found += ["sheriff_name", "auction_date_raw", "auction_time", "auction_venue"]

    m = _PHYSICAL_ADDRESS_RE.search(text)
    if m:
        result.physical_address = m.group("address").strip()
        result.fields_found.append("physical_address")

    m = _IMPROVEMENTS_RE.search(text)
    if m:
        result.improvements_text = " ".join(m.group("improvements").split())
        result.fields_found.append("improvements_text")

    m = _RESERVE_PRICE_RE.search(text)
    if m:
        result.reserve_price_raw = "R" + m.group("price").strip()
        result.fields_found.append("reserve_price_raw")

    m = _DEPOSIT_RE.search(text)
    if m:
        result.deposit_text = m.group("deposit").strip()
        result.fields_found.append("deposit_text")

    m = _CONTACT_BLOCK_RE.search(text)
    if m:
        block = m.group("block")
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if lines:
            # First non-phone/email line is treated as the organisation/person name.
            for ln in lines:
                if not _EMAIL_RE.search(ln) and not _PHONE_RE.search(ln) and "telephone" not in ln.lower():
                    result.contact_organisation = ln
                    break
        email_m = _EMAIL_RE.search(block)
        if email_m:
            result.contact_email = email_m.group(0)
        phone_m = _PHONE_RE.search(block)
        if phone_m:
            result.contact_phone = phone_m.group(0)
        if result.contact_organisation or result.contact_email or result.contact_phone:
            result.fields_found.append("contact")

    m = _TITLE_DEED_RE.search(text)
    if m:
        result.title_deed = m.group("deed")
        result.fields_found.append("title_deed")

    m = _REGISTRATION_DIVISION_RE.search(text)
    if m:
        result.registration_division = m.group("div")

    m = _PROVINCE_RE.search(text)
    if m:
        result.province = " ".join(m.group("province").split()).title()
        result.fields_found.append("province")

    m = _LAND_AREA_RE.search(text)
    if m:
        try:
            result.land_area_m2 = float(m.group("area").replace(" ", "").replace(",", ""))
        except ValueError:
            pass

    m = _BEDROOMS_RE.search(text)
    if m:
        result.bedrooms = _word_or_digit_to_int(m.group("num"))

    m = _BATHROOMS_RE.search(text)
    if m:
        result.bathrooms = _word_or_digit_to_int(m.group("num"))

    result.voetstoots = bool(_VOETSTOOTS_RE.search(text))
    result.sold_as_is = bool(_AS_IS_RE.search(text))

    m = _CONDITIONS_REF_RE.search(text)
    if m:
        result.conditions_of_sale_reference = m.group("ref").strip()

    result.erf = parse_erf(text)
    if result.erf.erf_number or result.erf.portion_number or result.erf.sectional_unit_number:
        result.fields_found.append("erf_number")

    key_found = sum(1 for f in _KEY_FIELDS if f in result.fields_found)
    result.extraction_confidence = round(key_found / len(_KEY_FIELDS), 2)

    return result
