"""Deterministic parsing of South African property/deeds descriptions.

Covers the example forms from the coding brief section 10:

  - Erf 1234 Midrand Extension 5 Township
  - Remaining Extent of Erf 123 Johannesburg
  - Portion 4 of Farm 100
  - Remaining Extent of Portion 2 of the Farm Example 456
  - Unit 12 of Sectional Title Scheme SS123/2009
  - Section No. 8 as shown on Sectional Plan SS45/2018
  - Holding 10 Agricultural Holdings
  - A unit consisting of section 4 and an undivided share in common property

Regex-first, deterministic, with a confidence score - no LLM dependency.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ErfParseResult:
    erf_number: str | None = None
    portion_number: str | None = None
    farm_number: str | None = None
    farm_name: str | None = None
    township: str | None = None
    extension: str | None = None
    sectional_title_scheme: str | None = None
    sectional_unit_number: str | None = None
    remaining_extent: bool = False
    matched_patterns: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "erf_number": self.erf_number,
            "portion_number": self.portion_number,
            "farm_number": self.farm_number,
            "farm_name": self.farm_name,
            "township": self.township,
            "extension": self.extension,
            "sectional_title_scheme": self.sectional_title_scheme,
            "sectional_unit_number": self.sectional_unit_number,
            "remaining_extent": self.remaining_extent,
        }


_ERF_RE = re.compile(r"\bERF\s+(?P<erf>\d+[A-Z]?)\b(?P<rest>[^,\n]*)", re.IGNORECASE)
_EXTENSION_RE = re.compile(r"EXTENSION\s+(?P<ext>\d+)", re.IGNORECASE)
_TOWNSHIP_RE = re.compile(
    r"ERF\s+\d+[A-Z]?\s+(?P<township>[A-Za-z0-9][A-Za-z0-9\s]*?)\s+TOWNSHIP", re.IGNORECASE
)
_PORTION_FARM_RE = re.compile(
    r"PORTION\s+(?P<portion>\d+)\s+OF\s+(?:THE\s+)?FARM\s+(?P<rest>[^,.\n]+?)"
    r"(?=$|,|\.|\n|\bIN\b|\bREGISTRATION\b)",
    re.IGNORECASE,
)
_FARM_NAME_AND_NUMBER_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z\s]*?)\s+(?P<num>\d+)$")
_FARM_NUMBER_ONLY_RE = re.compile(r"^\d+$")
_SECTIONAL_UNIT_SCHEME_RE = re.compile(
    r"UNIT\s+(?P<unit>\d+)\s+OF\s+SECTIONAL\s+TITLE\s+SCHEME\s+(?P<scheme>SS\s?\d+/\d{4})",
    re.IGNORECASE,
)
_SECTIONAL_PLAN_RE = re.compile(
    r"SECTION\s+(?:NO\.?\s*)?(?P<section>\d+)\s+(?:AS\s+SHOWN\s+ON\s+)?SECTIONAL\s+PLAN\s+"
    r"(?P<plan>SS\s?\d+/\d{4})",
    re.IGNORECASE,
)
_SECTION_ONLY_RE = re.compile(
    r"\bSECTION\s+(?P<section>\d+)\b(?!\s+OF)", re.IGNORECASE
)
_REMAINING_EXTENT_RE = re.compile(r"REMAINING\s+EXTENT", re.IGNORECASE)
_HOLDING_RE = re.compile(
    r"HOLDING\s+(?P<holding>\d+)\s+(?P<name>[A-Za-z\s]*?HOLDINGS)", re.IGNORECASE
)


def parse_erf(text: str) -> ErfParseResult:
    """Extract structured deeds-description fields from free text.

    Confidence is a simple field-coverage heuristic: more distinct,
    unambiguous fields matched -> higher confidence. Callers should treat
    anything below 0.5 as needing human review, per the brief's "confidence
    scores + human review fallback" requirement.
    """
    result = ErfParseResult()
    fields_matched = 0

    if _REMAINING_EXTENT_RE.search(text):
        result.remaining_extent = True

    m = _ERF_RE.search(text)
    if m:
        result.erf_number = m.group("erf").strip()
        result.matched_patterns.append("erf")
        fields_matched += 1

    m = _TOWNSHIP_RE.search(text)
    if m:
        result.township = " ".join(m.group("township").split()).title()
        result.matched_patterns.append("township")
        fields_matched += 1

    m = _EXTENSION_RE.search(text)
    if m:
        result.extension = m.group("ext")
        result.matched_patterns.append("extension")
        fields_matched += 1

    m = _PORTION_FARM_RE.search(text)
    if m:
        result.portion_number = m.group("portion")
        rest = m.group("rest").strip()
        name_num = _FARM_NAME_AND_NUMBER_RE.match(rest)
        if name_num:
            result.farm_name = " ".join(name_num.group("name").split()).title()
            result.farm_number = name_num.group("num")
        elif _FARM_NUMBER_ONLY_RE.match(rest):
            result.farm_number = rest
        else:
            result.farm_name = " ".join(rest.split()).title()
        result.matched_patterns.append("portion_farm")
        fields_matched += 1

    m = _SECTIONAL_UNIT_SCHEME_RE.search(text)
    if m:
        result.sectional_unit_number = m.group("unit")
        result.sectional_title_scheme = m.group("scheme").replace(" ", "")
        result.matched_patterns.append("sectional_unit_scheme")
        fields_matched += 2
    else:
        m = _SECTIONAL_PLAN_RE.search(text)
        if m:
            result.sectional_unit_number = m.group("section")
            result.sectional_title_scheme = m.group("plan").replace(" ", "")
            result.matched_patterns.append("sectional_plan")
            fields_matched += 2
        else:
            m = _SECTION_ONLY_RE.search(text)
            if m and re.search(r"SECTIONAL|COMMON\s+PROPERTY|UNDIVIDED\s+SHARE", text, re.IGNORECASE):
                result.sectional_unit_number = m.group("section")
                result.matched_patterns.append("section_only")
                fields_matched += 1

    m = _HOLDING_RE.search(text)
    if m and not result.erf_number and not result.portion_number:
        # Treat "Holding N ... Holdings" as an erf-like identifier for now.
        result.erf_number = m.group("holding")
        result.township = " ".join(m.group("name").split()).title()
        result.matched_patterns.append("holding")
        fields_matched += 1

    # Confidence: 0 fields -> 0.0, 1 field -> 0.4, 2 -> 0.7, 3+ -> 0.9
    result.confidence = {0: 0.0, 1: 0.4, 2: 0.7}.get(fields_matched, 0.9)
    return result
