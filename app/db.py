"""Database engine and session management.

Uses SQLite by default (file committed into the repo under data/) so there is
no database server to host or pay for. If this ever needs to grow beyond one
operator, DATABASE_URL can be pointed at a free-tier hosted Postgres
(Supabase / Neon) without changing any model code, since we stick to
SQLAlchemy 2.0 portable types.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base


def _ensure_sqlite_dir(database_url: str) -> None:
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.replace("sqlite:///", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables if they don't exist. No Alembic in the MVP - see docs/
    for how to introduce migrations once the schema needs to evolve."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
