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
| Manual upload       | Operator uploads a PDF/TXT notice into `data/inbox/` | N/A - no automated fetching involved | Sheriff-sale notices, parsed by `sheriff_notice_parser.py`. |
| MyRoof.co.za bank listings | Live collector (`app/collectors/sources/myroof.py`) | **Yes** | Standard Bank/FNB/Nedbank/SA Home Loans repossessed and assisted-sale listings. See "Why MyRoof cleared the bar" below. Filtered to the towns in `WATCH_AREAS`. |

Only one live collector is implemented, by design - see `app/collectors/base.py`.
The original brief's own instructions (and the `Source` model's compliance
fields in `app/models.py`) require every new source to have its terms of use
and robots.txt reviewed, and the result recorded, **before**
`automated_access_allowed` is set to `True` on that
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

## Why there's a reminder email instead of a live collector for sheriff sales

Researched in July 2026, for Potchefstroom/Fochville/Vereeniging specifically,
but the conclusion applies nationally: the two real sources for South African
sale-in-execution notices both fail the automated-access test in this policy.

- **SA Sheriff (sasheriff.co.za)** - every listing states "No article or
  picture may be reproduced/published without the written consent of SA
  Sheriff," and it's a paid subscription service (~R230/month).
- **News24 / Netwerk24 / SNL24 public notices** - usable only for
  "educational, research, non-commercial, private or personal use" per their
  terms, offer no alert/RSS/API feed for notices, and require a free login to
  view at all - i.e. they sit behind an access control, which this policy
  already rules out bypassing regardless of the copyright question.

Neither source is fetched or stored automatically anywhere in this codebase.
`app/services/area_watch.py` instead emails a plain reminder with direct
links, so the operator remembers to check by hand - it builds URLs, it never
requests either site's content. If SA Sheriff's paid subscription is ever
purchased, its notification emails would become a legitimate manual-forward
source (same pattern as `manual_upload.py`), since at that point the operator
is a licensed recipient of that data.

## Why MyRoof.co.za cleared the bar for a live collector

Checked the same way, MyRoof came out differently, so it's the one source in
this project with `automated_access_allowed = True`:

- **robots.txt** (fetched directly by the operator on 26 July 2026):
  ```
  User-Agent: *
  Disallow: /templates/
  Sitemap: https://www.myroof.co.za/sitemap.xml
  ```
  Only an internal assets folder is disallowed; every listing page is open,
  and a sitemap is published specifically so the site gets crawled.
- **No login wall** - listings are browsable by anyone, immediately.
- **No "do not reproduce" notice** was found anywhere on the site (unlike SA
  Sheriff's explicit copyright restriction on every listing).
- **Aligned incentives** - MyRoof hosts the banks' *own* official listings
  for Standard Bank, FNB, Nedbank, and SA Home Loans. The banks' commercial
  interest is for these properties to be found by buyers as fast as
  possible; that's the opposite incentive from a paid classifieds service.

`app/collectors/sources/myroof.py` still treats this as a privilege to use
carefully, not a blank cheque:

- Every fetch is checked against `robots.txt` **at runtime**, via
  `urllib.robotparser`, so a future policy change is respected automatically
  rather than relying on this document staying up to date.
- Only a small, fixed list of the banks' own program pages are crawled - not
  the general property-search engine - to keep total request volume low.
- A 1.5-second delay between requests, a real and contactable User-Agent
  string, and a hard cap (`MAX_DETAIL_FETCHES_PER_RUN`) on how many listing
  pages get fetched in a single run.
- Only listings with a recognisable bank "Seller Type" (EasySell, Quick
  Sell, Repossessed, Pre-Hammer, etc.) become opportunities - ordinary
  private listings on the same site are explicitly skipped, since they're
  out of scope for a *distressed*-property tool.

If MyRoof's `robots.txt` or terms ever change to restrict this, the fix is a
one-line change: set `automated_access_allowed = False` on its `Source` row
and the collector should be disabled or replaced with manual upload.
