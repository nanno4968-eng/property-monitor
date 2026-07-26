"""Lightweight, deterministic document classifier (brief section 9, step 4).

Keyword-based on purpose: route a document to the right parser, and reject
documents that are estate/insolvency notices with no actual sale advertised
(brief section 12 critical rule) before they ever become an "opportunity".
"""
from __future__ import annotations

import re

SHERIFF_SALE_MARKERS = (
    r"NOTICE OF SALE IN EXECUTION",
    r"SALE IN EXECUTION",
    r"SHERIFF OF [A-Z\s]+",
    r"PUBLIC AUCTION",
)

MUNICIPAL_DISPOSAL_MARKERS = (
    r"MUNICIPAL(?:ITY)?.{0,40}DISPOSAL",
    r"DISPOSAL OF (?:MUNICIPAL )?(?:LAND|PROPERTY|ERVEN)",
    r"COUNCIL RESOLUTION.{0,60}SELL",
)

ESTATE_NOTICE_ONLY_MARKERS = (
    r"NOTICE TO CREDITORS",
    r"LIQUIDATION AND DISTRIBUTION ACCOUNT",
    r"ESTATE LATE",
    r"DECEASED ESTATE",
)

SALE_ADVERTISED_MARKERS = (
    r"AUCTION",
    r"FOR SALE",
    r"TENDER",
    r"OFFERS TO PURCHASE",
    r"WILL BE SOLD",
)


def _any_match(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_document(text: str) -> str:
    """Return one of: sheriff_sale, municipal_disposal, estate_notice_only,
    unrelated, uncertain."""
    if not text or len(text.strip()) < 20:
        return "unrelated"

    if _any_match(SHERIFF_SALE_MARKERS, text):
        return "sheriff_sale"

    if _any_match(MUNICIPAL_DISPOSAL_MARKERS, text):
        return "municipal_disposal"

    if _any_match(ESTATE_NOTICE_ONLY_MARKERS, text):
        # Brief section 12 critical rule: an estate/insolvency notice alone,
        # with no advertised sale, must NOT become an opportunity.
        if _any_match(SALE_ADVERTISED_MARKERS, text):
            return "estate_notice_with_sale"
        return "estate_notice_only"

    if _any_match(SALE_ADVERTISED_MARKERS, text):
        return "uncertain"

    return "unrelated"
