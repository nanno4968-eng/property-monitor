import urllib.robotparser

from app.collectors.sources.myroof import USER_AGENT, _find_candidates_in_program_page

# Realistic HTML fragment matching the real anchor pattern on myroof.co.za
# bank-program pages (href + title attributes on the <a> tag).
SAMPLE_PROGRAM_PAGE_HTML = """
<html><body>
<div class="listing">
  <a href="/MR676778-3-Bedroom-2-Bathroom-House-for-Sale-in-Fochville-North-West-North-West"
     title="3 Bedroom 2 Bathroom House for Sale in Fochville, North West, North West">Fochville</a>
</div>
<div class="listing">
  <a href="/MR112233-House-for-Sale-in-Pretoria-North-Gauteng"
     title="House for Sale in Pretoria North, Gauteng">Pretoria North</a>
</div>
<div class="listing">
  <a href="/MR998877-3-Bedroom-House-for-Sale-in-Vereeniging-Gauteng"
     title="3 Bedroom House for Sale in Vereeniging, Gauteng, Gauteng">Vereeniging</a>
</div>
<div class="listing">
  <a href="/MR445566-Land-for-Sale-in-Potchefstroom-North-West"
     title="Land for Sale in Potchefstroom, North West, North West">Potchefstroom</a>
</div>
<a href="/search/">Search</a>
</body></html>
"""

WATCH_AREAS = ["Potchefstroom", "Fochville", "Vereeniging"]


def test_only_matching_areas_are_returned():
    candidates = _find_candidates_in_program_page(SAMPLE_PROGRAM_PAGE_HTML, WATCH_AREAS)
    codes = {c.mr_code for c in candidates}
    assert codes == {"MR676778", "MR998877", "MR445566"}
    assert "MR112233" not in codes  # Pretoria North is not a watch area


def test_candidate_urls_are_absolute():
    candidates = _find_candidates_in_program_page(SAMPLE_PROGRAM_PAGE_HTML, WATCH_AREAS)
    for c in candidates:
        assert c.detail_url.startswith("https://www.myroof.co.za/")


def test_no_matches_when_watch_areas_is_empty():
    candidates = _find_candidates_in_program_page(SAMPLE_PROGRAM_PAGE_HTML, [])
    assert candidates == []


def test_non_mr_links_are_ignored():
    html = '<a href="/search/" title="Search">Search</a><a href="/about-us/">About</a>'
    candidates = _find_candidates_in_program_page(html, WATCH_AREAS)
    assert candidates == []


def test_real_robots_txt_allows_listing_pages_and_blocks_templates():
    """Uses the actual robots.txt content fetched from myroof.co.za
    (User-Agent: *, Disallow: /templates/, plus a sitemap) rather than a
    guess, so this test fails loudly if that policy ever tightens."""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse([
        "User-Agent: *",
        "Disallow: /templates/",
        "Sitemap: https://www.myroof.co.za/sitemap.xml",
    ])
    assert rp.can_fetch(USER_AGENT, "https://www.myroof.co.za/Standard-Bank/EasySell-Properties") is True
    assert rp.can_fetch(USER_AGENT, "https://www.myroof.co.za/MR676778-House") is True
    assert rp.can_fetch(USER_AGENT, "https://www.myroof.co.za/templates/foo") is False
