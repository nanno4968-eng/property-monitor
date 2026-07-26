# Architecture

## Why this looks different from a typical "distressed property platform"

The original design brief for this project specifies a full multi-user
platform: FastAPI + PostgreSQL/PostGIS + Celery/Redis + a React dashboard,
running behind authentication, with live scheduled scrapers. That is a great
target architecture once this has a paying team of analysts behind it - but
it needs an always-on server, a hosted database, and a worker queue, none of
which are free to run continuously.

This edition targets a single operator who wants a **standing screening
pipeline with zero ongoing hosting cost**. To get there, three deliberate
substitutions were made:

| Brief's suggestion              | This edition                               | Why it's still $0 |
|----------------------------------|---------------------------------------------|--------------------|
| PostgreSQL + PostGIS server      | SQLite file committed into the repo          | No database to host; git history is a free audit trail |
| Celery + Redis worker queue      | A single synchronous pipeline run per Action | MVP volume (a handful of manually-uploaded notices per run) doesn't need a queue |
| FastAPI + React dashboard        | A PDF report emailed after each run          | No server process needs to stay up between runs |

Everything else - the data model, the parsing approach, the scoring rules,
the risk flags, the deduplication logic, the "human must verify" workflow -
follows the original brief as closely as the simplified runtime allows.

## Runtime model

There is no server. The GitHub Actions workflow (`.github/workflows/collect.yml`)
*is* the runtime:

1. A scheduled (or manually triggered, or push-triggered) Action checks out
   the repo.
2. It installs Python + the system libraries WeasyPrint needs for PDF
   rendering.
3. It runs `python -m app.cli run`, which:
   - scans `data/inbox/` for new PDF/TXT notices (the manual-upload collector),
   - classifies, parses, normalises, deduplicates, scores, and risk-flags them,
   - writes everything to `data/property_monitor.db` (SQLite),
   - renders a PDF report of anything new/updated this run,
   - emails it via SMTP if credentials are configured.
4. The Action commits the updated database and archived source documents
   back into the repository.

Running it again with an empty inbox is a fast no-op.

## Upgrading later

If this grows past what SQLite/Actions comfortably handles:

- **Database**: point `DATABASE_URL` at a free-tier hosted Postgres
  (Supabase or Neon both have $0 tiers). The SQLAlchemy models don't use any
  SQLite-specific types, so this is a config change, not a rewrite - add
  Alembic at that point for real migrations.
- **Worker queue**: if collection volume grows enough that a single Action
  run can't finish in time, introduce Celery + Redis (or just fan out into
  multiple Actions matrix jobs, which is still free).
- **Dashboard**: the original brief's FastAPI + React design in
  `docs/data_dictionary.md`-style detail slots in cleanly on top of the
  existing `app/models.py` schema - add `app/api/` and a `frontend/` app
  without touching the collectors/parsers/services layer.
- **Live collectors**: add new files under `app/collectors/sources/`
  following the `manual_upload.py` pattern, but only after recording a
  compliance review (robots.txt, terms of use, rate limit) on the
  corresponding `Source` row - see `docs/source_policy.md`.
