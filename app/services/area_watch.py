"""Area watch reminder.

This is deliberately NOT a scraper. Research into the two real sources for
South African sale-in-execution notices found:

- SA Sheriff (sasheriff.co.za): every listing states "No article or picture
  may be reproduced/published without the written consent of SA Sheriff",
  and it's a paid subscription service.
- News24 / Netwerk24 / SNL24 public notices: usable only for "educational,
  research, non-commercial, private or personal use" per their terms, offer
  no alert/RSS feed for notices, and require a free login to view at all.

Per this project's "legal access only" principle (docs/source_policy.md),
neither is fetched or stored automatically. This module only builds an email
containing plain links, so the operator remembers to go look, by hand, for
the configured areas - it never touches either site's content.
"""
from __future__ import annotations

from app.config import settings
from app.services.emailer import send_html_email

NEWS24_NOTICES_URL = "https://www.news24.com/notices"
SASHERIFF_AUCTIONS_URL = "https://www.sasheriff.co.za/au1/"
SASHERIFF_HOME_URL = "https://www.sasheriff.co.za/"


def get_watch_areas() -> list[str]:
    return [a.strip() for a in settings.watch_areas.split(",") if a.strip()]


def build_reminder_html(areas: list[str]) -> str:
    area_rows = "".join(
        f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:bold;">{area}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;">
            <a href="{NEWS24_NOTICES_URL}">News24 Public Notices</a><br>
            <span style="color:#666;font-size:12px;">Log in (free), then search "{area}"</span>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;">
            <a href="{SASHERIFF_AUCTIONS_URL}">SA Sheriff auctions</a><br>
            <span style="color:#666;font-size:12px;">Search "{area}"</span>
          </td>
        </tr>
        """
        for area in areas
    )
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#222;">
    <h2 style="margin-bottom:4px;">Weekly area-check reminder</h2>
    <p style="color:#444;">
      Neither site below lets this pipeline check automatically on your behalf - SA Sheriff
      restricts automated copying of its listings, and News24's public notices require being
      logged in to view. So this is just a reminder with direct links for the areas you're
      tracking: a five-minute manual look, not an automated report.
    </p>
    <table style="border-collapse:collapse;width:100%;margin-top:16px;">
      <tr style="background:#f5f5f5;">
        <th style="padding:10px 14px;text-align:left;">Area</th>
        <th style="padding:10px 14px;text-align:left;">Newspaper notices</th>
        <th style="padding:10px 14px;text-align:left;">Sheriff auctions</th>
      </tr>
      {area_rows}
    </table>
    <p style="margin-top:20px;">
      Found something real for one of these areas? Add it to <code>data/inbox</code> on GitHub
      the same way as before, and the pipeline will read, score, and email you about it
      automatically on its next run.
    </p>
    <p style="font-size:12px;color:#777;margin-top:24px;border-top:1px solid #eee;padding-top:12px;">
      Want this fully hands-off instead? SA Sheriff's paid subscription (roughly R230/month)
      includes free notifications when new properties become available in your chosen areas -
      a properly licensed way to get automatic alerts. See
      <a href="{SASHERIFF_HOME_URL}">sasheriff.co.za</a> for details.
    </p>
    </body></html>
    """


def send_watch_reminder() -> bool:
    areas = get_watch_areas()
    if not areas:
        print("[area_watch] No watch areas configured (WATCH_AREAS) - skipping.")
        return False
    html = build_reminder_html(areas)
    subject = f"Property monitor: weekly check reminder ({', '.join(areas)})"
    return send_html_email(subject, html)


if __name__ == "__main__":
    send_watch_reminder()
