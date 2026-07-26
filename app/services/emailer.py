"""Email delivery via plain smtplib - deliberately provider-agnostic so any
free-tier SMTP relay works (Brevo, Gmail app-password, Mailgun sandbox, etc).
No paid email API required.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.config import settings


def send_report_email(subject: str, html_body: str, pdf_path: Path | None) -> bool:
    """Returns True if sent, False if SMTP isn't configured (logged, not raised,
    so a missing secret doesn't crash the whole pipeline run)."""
    if not (settings.smtp_host and settings.smtp_username and settings.smtp_password and settings.alert_email_to):
        print("[emailer] SMTP not fully configured - skipping send. Set SMTP_* and ALERT_EMAIL_TO.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.alert_email_to
    msg.set_content("This report requires an HTML-capable email client. A PDF copy is attached.")
    msg.add_alternative(html_body, subtype="html")

    if pdf_path and pdf_path.exists():
        msg.add_attachment(
            pdf_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)

    print(f"[emailer] Report sent to {settings.alert_email_to}")
    return True
