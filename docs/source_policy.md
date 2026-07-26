# Source policy

This project only ever uses lawful sale channels and lawful access methods.
It must **not**:

- claim abandoned property, or acquire property via unpaid municipal rates;
- identify homes for unlawful occupation;
- contact debtors or occupants automatically;
- bypass logins, paywalls, CAPTCHAs, or other access controls;
- scrape a source whose terms or robots.txt prohibit automated access;
- represent any property as legally transferable without independent verification;
- provide legal advice.

## Current sources

| Source            | Access method   | Automated access allowed? | Notes |
|--------------------|------------------|-----------------------------|-------|
| Manual upload       | Operator uploads a PDF/TXT notice into `data/inbox/` | N/A - no automated fetching involved | The only collector implemented so far. |

No live scrapers or feed collectors are implemented yet, by design - see
`app/collectors/base.py`. The original brief's own instructions (and the
`Source` model's compliance fields in `app/models.py`) require every new
source to have its terms of use and robots.txt reviewed, and the result
recorded, **before** `automated_access_allowed` is set to `True` on that
source's row. Treat this as a hard gate, not a formality: a source with
`automated_access_allowed = False` should only ever be exercised through
manual upload or a licensed/permitted feed.

## Adding a new source

1. Read the source's terms of use and `robots.txt`. Record the outcome.
2. Create (or update) its `Source` row with `robots_policy_checked`,
   `terms_checked`, `automated_access_allowed`, and `legal_notes` filled in
   honestly.
3. If automated access is **not** permitted, stop - route that source
   through manual upload instead, or look for a licensed data feed / API the
   provider offers.
4. If automated access **is** permitted, add a new collector under
   `app/collectors/sources/` (mirroring `manual_upload.py`'s shape), respect
   any stated rate limit, and add a parser under `app/parsers/` if the
   document format differs from the sheriff-notice format already handled.
5. Add fixtures and tests before wiring it into `app/pipeline.py`.

## A notice alone is not an opportunity

Per the brief's critical rule: a deceased-estate or insolvency notice that
does **not** advertise an authorised sale, auction, or marketing listing
must never become an "opportunity" record. `app/parsers/classify.py`
implements this as a hard gate - documents classified as
`estate_notice_only` are recorded (for audit purposes) but never turned into
an `Opportunity`.
