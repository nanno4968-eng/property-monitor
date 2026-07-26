"""MyRoof.co.za bank-listing collector.

The only live (non-manual-upload) collector in this project, because it's
the only source that cleared the compliance bar - see
docs/source_policy.md for the full reasoning:

- robots.txt (checked by the operator, recorded below) disallows only
  /templates/, and a sitemap.xml is published - i.e. crawling is invited.
- No login wall, no "do not reproduce" notice (unlike SA Sheriff/News24).
- The banks' own commercial interest is for these listings to be found.

Design, to be a good citizen and minimise load on the target site:
1. Fetch a small, fixed list of national bank-program pages (not the
   general property-search engine) - these are inherently low-volume
   (repossessions are relatively rare) compared to crawling all general
   listings.
2. Filter candidates by matching the configured watch-area town name
   against the listing's own title text - zero extra requests for this step.
3. Only for actual matches, fetch that one listing's detail page to pull
   clean structured fields (price, beds, baths, seller type).
4. A short delay between requests; a real, contactable User-Agent; and a
   hard cap on total requests per run.

Every fetch is checked against robots.txt at runtime (not just once by a
human) via urllib.robotparser, so a future robots.txt change is respected
automatically rather than relying on this comment staying accurate.
"""
from __future__ import annotations

import hashlib
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import settings

BASE_URL = "https://www.myroof.co.za"
USER_AGENT = (
    "distressed-property-monitor/1.0 "
    "(+https://github.com/ - operator-run compliance research tool; "
    "see docs/source_policy.md; robots.txt checked before every fetch)"
)
REQUEST_DELAY_SECONDS = 1.5
MAX_DETAIL_FETCHES_PER_RUN = 25

# National bank-program listing pages - deliberately not the general search
# engine, to keep request volume low and stay clearly inside "bank listings
# only" territory.
BANK_PROGRAM_PAGES = [
    "/Standard-Bank/EasySell-Properties",
    "/Standard-Bank/Repossessed-Properties",
    "/Standard-Bank/Insolvent-Properties",
    "/Standard-Bank/Sheriff-Auctions",
    "/pre-hammer/",
    "/FNB/Quick-Sell",
    "/FNB/Repossessed-Properties",
    "/FNB/Bank-Owned",
    "/Nedbank/Repossessed-Properties",
    "/SAHomeLoans/Sell-Assist-Properties",
    "/SAHomeLoans/Repossessed-Properties",
]

_MR_HREF_RE = re.compile(r"^/MR(\d+)-")

_robots_parser: urllib.robotparser.RobotFileParser | None = None


def _get_robots_parser() -> urllib.robotparser.RobotFileParser:
    global _robots_parser
    if _robots_parser is None:
        _robots_parser = urllib.robotparser.RobotFileParser()
        _robots_parser.set_url(f"{BASE_URL}/robots.txt")
        try:
            _robots_parser.read()
        except Exception:
            pass  # fail closed via can_fetch's default (True) only if read succeeded;
            # if it didn't, we still try can_fetch, which returns True when no
            # rules were loaded - acceptable here since a human already
            # verified robots.txt manually (see docs/source_policy.md).
    return _robots_parser


def _allowed(url: str) -> bool:
    return _get_robots_parser().can_fetch(USER_AGENT, url)


@dataclass
class MyRoofCandidate:
    mr_code: str
    detail_url: str
    title: str
    matched_area: str


@dataclass
class MyRoofFetchedListing:
    mr_code: str
    detail_url: str
    matched_area: str
    page_text: str
    content_hash: str


def _fetch(url: str, session_http) -> str | None:
    if not _allowed(url):
        print(f"[myroof] robots.txt disallows {url} - skipping.")
        return None
    try:
        resp = session_http.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        print(f"[myroof] fetch failed for {url}: {exc}")
        return None


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _find_candidates_in_program_page(html: str, watch_areas: list[str]) -> list[MyRoofCandidate]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[MyRoofCandidate] = []
    seen_codes: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _MR_HREF_RE.match(href)
        if not m:
            continue
        # Prefer the title attribute (fuller text, e.g. "...for Sale in
        # Fochville, North West, North West"); fall back to link text.
        title = a.get("title") or a.get_text(strip=True) or ""
        for area in watch_areas:
            if re.search(rf"\b{re.escape(area)}\b", title, re.IGNORECASE):
                code = f"MR{m.group(1)}"
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                candidates.append(MyRoofCandidate(
                    mr_code=code,
                    detail_url=BASE_URL + href if href.startswith("/") else href,
                    title=title,
                    matched_area=area,
                ))
                break
    return candidates


def collect_myroof_listings() -> list[MyRoofFetchedListing]:
    """Returns fully-fetched, matched bank-listing pages ready for parsing.
    Never raises on network/parsing problems for a single page - logs and
    continues, so one bad fetch doesn't kill the whole run."""
    import requests

    watch_areas = [a.strip() for a in settings.watch_areas.split(",") if a.strip()]
    if not watch_areas:
        return []

    http = requests.Session()
    results: list[MyRoofFetchedListing] = []
    all_candidates: list[MyRoofCandidate] = []

    for path in BANK_PROGRAM_PAGES:
        url = BASE_URL + path
        html = _fetch(url, http)
        time.sleep(REQUEST_DELAY_SECONDS)
        if not html:
            continue
        candidates = _find_candidates_in_program_page(html, watch_areas)
        all_candidates.extend(candidates)

    # De-duplicate across program pages (a listing could theoretically be
    # linked from more than one program page).
    unique_candidates = {c.mr_code: c for c in all_candidates}.values()

    for candidate in list(unique_candidates)[:MAX_DETAIL_FETCHES_PER_RUN]:
        html = _fetch(candidate.detail_url, http)
        time.sleep(REQUEST_DELAY_SECONDS)
        if not html:
            continue
        text = _html_to_text(html)
        content_hash = hashlib.sha256(f"myroof:{candidate.mr_code}".encode()).hexdigest()
        results.append(MyRoofFetchedListing(
            mr_code=candidate.mr_code,
            detail_url=candidate.detail_url,
            matched_area=candidate.matched_area,
            page_text=text,
            content_hash=content_hash,
        ))

    return results
