"""Manual-upload collector (brief section 22: first source adapter).

Drop a .txt or .pdf sheriff-sale (or other) notice into data/inbox/, commit
and push (or run locally) - the pipeline picks it up, archives the original
under data/raw_documents/, and creates a RawDocument row keyed by SHA-256 so
the same file is never processed twice.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CollectionRun, RawDocument, Source
from app.parsers.text_cleaning import clean_whitespace, extract_text_from_pdf

SUPPORTED_SUFFIXES = {".txt", ".pdf"}


def _get_or_create_manual_source(session: Session) -> Source:
    existing = session.execute(
        select(Source).where(Source.collector_name == "manual_upload")
    ).scalar_one_or_none()
    if existing:
        return existing
    source = Source(
        name="Manual upload",
        source_type="manual_upload",
        access_method="manual_upload",
        collector_name="manual_upload",
        parser_name="sheriff_notice_parser",
        robots_policy_checked=True,
        terms_checked=True,
        automated_access_allowed=False,
        legal_notes="Operator-supplied documents only. No automated fetching involved.",
    )
    session.add(source)
    session.flush()
    return source


def collect_from_inbox(session: Session) -> tuple[CollectionRun, list[RawDocument]]:
    source = _get_or_create_manual_source(session)
    run = CollectionRun(source_id=source.id, status="running")
    session.add(run)
    session.flush()

    new_documents: list[RawDocument] = []
    inbox = settings.inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    settings.raw_document_archive_dir.mkdir(parents=True, exist_ok=True)

    candidate_files = sorted(
        p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    run.items_found = len(candidate_files)

    for path in candidate_files:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > settings.max_upload_mb:
            continue  # brief section 20: file size limits

        content_bytes = path.read_bytes()
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        already_seen = session.execute(
            select(RawDocument).where(RawDocument.content_hash == content_hash)
        ).scalar_one_or_none()
        if already_seen:
            continue

        if path.suffix.lower() == ".pdf":
            document_type = "pdf"
            text = extract_text_from_pdf(path)
        else:
            document_type = "text"
            text = clean_whitespace(content_bytes.decode("utf-8", errors="replace"))

        archive_path = settings.raw_document_archive_dir / f"{content_hash}{path.suffix.lower()}"
        if not archive_path.exists():
            shutil.copy2(path, archive_path)

        raw_doc = RawDocument(
            source_id=source.id,
            collection_run_id=run.id,
            source_url=None,
            document_type=document_type,
            title=path.name,
            retrieved_at=datetime.now(UTC),
            content_hash=content_hash,
            original_path=str(archive_path),
            extracted_text=text,
            parser_version="sheriff_notice_parser:1",
            processing_status="pending",
            metadata_json={"original_filename": path.name, "size_bytes": len(content_bytes)},
        )
        session.add(raw_doc)
        session.flush()
        new_documents.append(raw_doc)

        # Move the processed file out of the inbox so re-running doesn't reprocess it
        # (it's already archived under raw_document_archive_dir with its checksum).
        processed_marker = inbox / "processed"
        processed_marker.mkdir(exist_ok=True)
        shutil.move(str(path), str(processed_marker / path.name))

    run.documents_created = len(new_documents)
    run.completed_at = datetime.now(UTC)
    run.status = "success"
    source.last_success_at = run.completed_at

    return run, new_documents
