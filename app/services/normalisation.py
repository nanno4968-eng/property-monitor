"""Normalisation service (brief section 6 / 9 step 6).

Deliberately conservative: if something can't be parsed with confidence, it
is returned as None rather than guessed, per the "no false precision"
principle. Money always becomes Decimal, never float.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from dateutil import parser as dateutil_parser

from app.config import settings

PROVINCE_ALIASES = {
    "gauteng": "Gauteng",
    "western cape": "Western Cape",
    "eastern cape": "Eastern Cape",
    "kwazulu-natal": "KwaZulu-Natal",
    "kwazulu natal": "KwaZulu-Natal",
    "kzn": "KwaZulu-Natal",
    "free state": "Free State",
    "limpopo": "Limpopo",
    "mpumalanga": "Mpumalanga",
    "north west": "North West",
    "northern cape": "Northern Cape",
}

_ADDRESS_ABBREVIATIONS = {
    r"\bSTR\.?\b": "Street",
    r"\bRD\.?\b": "Road",
    r"\bAVE?\.?\b": "Avenue",
    r"\bDR\.?\b": "Drive",
    r"\bEXT\.?\b": "Extension",
    r"\bBLVD\.?\b": "Boulevard",
}


def parse_sa_date(raw: str | None) -> datetime | None:
    """Parse South African date formats such as '18 August 2026'.

    Notices rarely state a timezone explicitly; since these are South African
    legal notices, a naive result is assumed to be in Africa/Johannesburg
    (SAST) rather than left ambiguous, so it stays comparable to tz-aware
    UTC datetimes elsewhere in the app.
    """
    if not raw:
        return None
    try:
        parsed = dateutil_parser.parse(raw.strip(), dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(settings.default_timezone))
    return parsed


def parse_price(raw: str | None) -> Decimal | None:
    """Parse 'R850,000' / 'R 850 000.00' / 'R850000' into a Decimal."""
    if not raw:
        return None
    cleaned = re.sub(r"[Rr]\s?", "", raw)
    cleaned = cleaned.replace(" ", "").replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalise_province(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return PROVINCE_ALIASES.get(key, raw.strip().title())


def normalise_address(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    for pattern, replacement in _ADDRESS_ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,")
