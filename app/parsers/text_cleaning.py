"""Shared text-cleaning and PDF text-extraction helpers."""
from __future__ import annotations

import re
from pathlib import Path


def clean_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from a PDF, preferring pdfplumber (better layout handling)
    and falling back to pypdf. OCR is intentionally not wired up in the MVP -
    scanned/image-only notices will fall through to the manual review queue
    with a low extraction confidence instead of silently failing."""
    text_parts: list[str] = []
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(f"[page {i}]\n{page_text}")
    except Exception:
        text_parts = []

    if not text_parts:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            for i, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(f"[page {i}]\n{page_text}")
        except Exception:
            pass

    return clean_whitespace("\n\n".join(text_parts))
