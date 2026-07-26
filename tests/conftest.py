"""Test configuration: point the app at a throwaway temp directory so tests
never touch the real data/ folder, and reset the database between tests."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="dpm_test_"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_ROOT / 'test.db'}")
os.environ.setdefault("INBOX_DIR", str(_TMP_ROOT / "inbox"))
os.environ.setdefault("RAW_DOCUMENT_ARCHIVE_DIR", str(_TMP_ROOT / "raw_documents"))
os.environ.setdefault("REPORTS_DIR", str(_TMP_ROOT / "reports"))
os.environ.setdefault("GEOCODING_ENABLED", "false")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALWAYS_SEND_DIGEST", "false")

import pytest


@pytest.fixture(autouse=True)
def _no_live_network_calls(monkeypatch):
    """The MyRoof collector makes real HTTP requests in production. Tests
    must stay fast, deterministic, and offline - so every test gets an
    empty-list stand-in unless a specific test overrides this itself.
    Dedicated parser/collector-logic tests exercise the real parsing code
    against fixture HTML/text instead of hitting the network."""
    monkeypatch.setattr("app.pipeline.collect_myroof_listings", lambda: [])


@pytest.fixture()
def clean_db():
    """Fresh tables for a single test."""
    from app.db import engine, init_db
    from app.models import Base

    Base.metadata.drop_all(engine)
    init_db()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def clean_inbox():
    from app.config import settings

    if settings.inbox_dir.exists():
        shutil.rmtree(settings.inbox_dir)
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    yield settings.inbox_dir
    shutil.rmtree(settings.inbox_dir, ignore_errors=True)
