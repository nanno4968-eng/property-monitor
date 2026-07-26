"""Base collector interface.

Every source gets its own adapter (brief core principle 8: modular
collectors) so a broken or newly-added source never touches the others.
Live web collectors (RSS/HTML/gazette adapters) are intentionally NOT
implemented yet - brief section 30 explicitly defers live scraping past the
foundation step, and every live source needs its robots.txt / terms checked
and recorded on the Source row (section 19) before automated_access_allowed
may be set True. Add them under sources/ following the same pattern as
manual_upload.py once that review is done.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CollectedItem:
    """One discovered document, prior to being written to the database."""
    document_type: str
    title: str | None
    source_url: str | None
    raw_bytes: bytes | None
    text: str | None
    publication_date_raw: str | None = None
    metadata: dict = field(default_factory=dict)
