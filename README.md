# South African Distressed Property Opportunity Monitor

A screening pipeline for **lawful** distressed-property sale channels in
South Africa (sheriff sales in execution, bank repossessions, insolvent- and
deceased-estate sales, municipal disposals, authorised auctions). It parses
notices, deduplicates them, scores them conservatively, flags risks, and
emails you a PDF report. It does **not** buy, contact debtors/occupants, or
claim ownership of anything - see `docs/source_policy.md` and
`docs/privacy_and_compliance.md` for the hard boundaries.

This edition is built to run for **$0/month**. See `docs/architecture.md`
for exactly how, and how to upgrade later if you outgrow it.

## What it actually costs

| Piece | Cost |
|---|---|
| Compute (GitHub Actions, scheduled) | Free (public repo: unlimited minutes; private repo: 2,000 min/month free tier, and a run here takes under a minute) |
| Database (SQLite, committed to the repo) | Free |
| Email delivery | Free tier of any SMTP provider - Brevo gives 300 emails/day free with no credit card; Gmail app-password works fine at low volume |
| Geocoding (optional) | Free (OpenStreetMap Nominatim, rate-limited) |
| PDF rendering | Free (WeasyPrint, open source) |

## How it works

1. Drop a sheriff-sale (or other) notice - `.pdf` or `.txt` - into
   `data/inbox/`.
2. Commit and push (or just run it locally).
3. The pipeline: archives the original, extracts and classifies the text,
   parses it deterministically (regex, not an LLM - see
   `docs/scoring_model.md`), deduplicates against existing opportunities,
   generates risk flags, calculates three separate scores (opportunity /
   risk / completeness), builds a due-diligence checklist, and emails you a
   PDF report of anything new or updated.
4. Everything - the database, the archived source documents, the audit log -
   lives in the repo, so git history doubles as your audit trail.

## Quick start (local)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# edit .env if you want email alerts - optional for a first test run

cp sample_data/sample_sheriff_notice.txt data/inbox/my_notice.txt
python -m app.cli run
```

Check `data/reports/` for the generated PDF, and query
`data/property_monitor.db` (any SQLite browser, or `sqlite3
data/property_monitor.db`) to see the structured records.

## Quick start (GitHub Actions - the $0 "production" path)

1. Push this repo to your own GitHub account.
2. **Settings -> Secrets and variables -> Actions -> New repository secret**,
   add:
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`
   - `ALERT_EMAIL_TO` (where you want reports sent)

   A free option: sign up at [Brevo](https://www.brevo.com) (300 emails/day
   free, no card required), create an SMTP key, and use their SMTP relay.
   Gmail with an [app password](https://myaccount.google.com/apppasswords)
   also works for personal, low-volume use.
3. **Settings -> Actions -> General**, confirm Actions are enabled and that
   "Read and write permissions" is set for the workflow (needed so it can
   commit the updated database back).
4. Drop a notice into `data/inbox/`, commit, and push - or just trigger the
   workflow manually from the **Actions** tab (**Property monitor - collect
   and report -> Run workflow**).
5. Check your inbox. Check `data/` in the repo for the updated database and
   audit trail.

The schedule (`.github/workflows/collect.yml`) defaults to a daily 06:00
SAST run - edit the cron expression to taste.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

36 tests cover the erf/deeds-description parser (all example forms from the
brief), the sheriff-notice parser (validated against the brief's own sample
fixture), deduplication scoring, risk flags, the scoring engine, and a full
pipeline integration test (including a duplicate-merge scenario).

## What's implemented vs deferred

**Implemented:** manual-upload collector, a live collector for
MyRoof.co.za's bank-repossession listings (Standard Bank/FNB/Nedbank/SA Home
Loans, filtered to your configured `WATCH_AREAS`), sheriff-sale notice
parsing, erf/portion/farm/sectional-title parsing, normalisation,
deduplication, risk-flag engine, three-part scoring, default due-diligence
checklist, PDF report generation, email delivery, a weekly area-check
reminder for sources that can't be automated, full audit trail, automated
tests.

**Deliberately deferred** (see `docs/architecture.md` for why, and how to
add them later): live collectors for sheriff-sale-notice sources - SA
Sheriff and News24/Netwerk24 public notices were both researched and found
to explicitly restrict automated copying (see `docs/source_policy.md`), so
those stay manual/reminder-based unless that changes. Also deferred: a web
dashboard and map, user accounts/auth, financial/valuation modelling, OCR
for scanned notices, Alembic migrations, Celery/Redis.

## The MyRoof live collector

`app/collectors/sources/myroof.py` checks MyRoof.co.za's own bank-listing
pages (Standard Bank EasySell/Pre-Hammer/Repossessed, FNB Quick
Sell/Repossessed, Nedbank Repossessed, SA Home Loans Sell Assist/Repossessed)
for anything matching your `WATCH_AREAS` towns, and feeds matches straight
into the same scoring/report/email pipeline as manually-uploaded notices.
This was the one source out of several researched that clearly permits
automated access - see `docs/source_policy.md` for the full compliance
review, including the actual `robots.txt` it was checked against. It runs
automatically as part of the same daily `python -m app.cli run` - no
separate setup needed.

## Repository layout

```
app/
  config.py, db.py, models.py       - settings, DB session, schema
  collectors/manual_upload.py       - the only live collector so far
  parsers/                          - classify, erf parser, sheriff-notice parser
  services/                         - normalisation, dedup, risk, scoring,
                                       due-diligence checklist, report, email, geocoding
  pipeline.py, cli.py               - orchestration + entry point
templates/report.html.j2            - the emailed report's HTML/PDF template
sample_data/                        - fixture used by the parser tests
tests/                              - unit + integration tests
docs/                                - architecture, scoring, source policy, privacy
.github/workflows/collect.yml       - the scheduled "server"
```

## Disclaimer

This platform identifies publicly advertised property opportunities and
assists with preliminary research. It does not provide legal, financial,
conveyancing, valuation, auction, or investment advice. Listings may be
incomplete, postponed, cancelled, outdated, occupied, or subject to
conditions not captured by the platform. Independently verify ownership,
title, authority to sell, auction status, property condition, occupation,
municipal accounts, levies, taxes, costs, and legal requirements before
making any decision or payment.
