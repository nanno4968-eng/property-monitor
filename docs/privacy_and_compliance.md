# Privacy and compliance

## Principles this pipeline follows

- **No public database of distressed owners.** Debtor and occupant names are
  never extracted or stored - only public organisational contacts (sheriff,
  bank, auctioneer, attorney, municipality) via the `Contact` model, and only
  where they appear as the official point of contact in a public notice.
- **No automated contact with debtors or occupants.** This pipeline never
  sends outbound communication to anyone other than the operator (the person
  running it), via the configured `ALERT_EMAIL_TO` address.
- **Human verification required.** Every opportunity is created with
  `status="new"` or `"needs_review"`, never `"verified"`. A standing
  `title_or_deeds_verification_outstanding` risk flag is attached to every
  opportunity until a human clears it through actual Deeds Office
  verification - see `docs/scoring_model.md` and `app/services/risk_engine.py`.
- **Source transparency and audit trail.** Every `SourceListing` links back
  to its `RawDocument`, which stores a SHA-256 checksum, retrieval
  timestamp, and the archived original file. `AuditLog` records every
  create/merge/reject decision the pipeline makes. Because the database
  itself is committed to git, the audit trail also benefits from git's own
  history and diff tooling for free.
- **No false precision.** Anything the parser couldn't determine is stored
  as `None`/unknown rather than guessed, and unknown values always reduce
  (never inflate) the opportunity score - see `docs/scoring_model.md`.
- **Secrets stay out of the repo.** SMTP credentials and the alert
  recipient live in GitHub Actions secrets (or a local, gitignored `.env`),
  never in code or committed config.
- **Legal access only.** See `docs/source_policy.md` - no collector may
  bypass a login, paywall, CAPTCHA, or robots.txt restriction, and no source
  is marked `automated_access_allowed=True` without a recorded compliance
  review.

## Data retention

Because SQLite + archived documents are committed straight into the repo,
retention is effectively "as long as the git repository exists." If you need
to remove a specific record (e.g. a mistakenly-uploaded document containing
personal information beyond what this pipeline is designed to store), you
will need to both delete the row and rewrite git history for the relevant
blob (`git filter-repo` or GitHub's own removal tooling), since a plain
`git revert` does not remove data from history.

## Disclaimer shown in every report

Every generated report (see `templates/report.html.j2`) includes the
brief's required disclaimer: this platform identifies publicly advertised
property opportunities and assists with preliminary research only. It does
not provide legal, financial, conveyancing, valuation, auction, or
investment advice, and every field must be independently verified before
any decision or payment is made.
