"""Default due-diligence checklist (brief section 15), condensed to the
items that apply to every shortlisted opportunity regardless of type."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import DueDiligenceItem, Opportunity

DEFAULT_CHECKLIST: list[tuple[str, str]] = [
    ("legal_and_title", "Confirm source notice is authentic"),
    ("legal_and_title", "Obtain and review the conditions of sale"),
    ("legal_and_title", "Verify registered property description against the Deeds Office"),
    ("legal_and_title", "Verify title deed, bonds, and endorsements"),
    ("legal_and_title", "Confirm auction/sale authority and that the sale is still active"),
    ("occupation", "Confirm whether the property is occupied"),
    ("occupation", "Assess vacant-possession terms and eviction risk"),
    ("municipal_and_levy", "Obtain municipal account information where lawfully available"),
    ("municipal_and_levy", "Confirm body corporate levies (if sectional title)"),
    ("physical", "Arrange external inspection"),
    ("physical", "Arrange internal inspection where allowed, and estimate repairs"),
    ("financial", "Confirm deposit deadline, buyer's premium, and VAT treatment"),
    ("financial", "Confirm balance-payment deadline and financing availability"),
    ("financial", "Estimate resale/rental value and set a minimum acceptable margin"),
    ("final_approval", "Attorney/conveyancer review before committing funds"),
]


def create_default_checklist(session: Session, opportunity: Opportunity) -> None:
    for category, title in DEFAULT_CHECKLIST:
        session.add(DueDiligenceItem(
            opportunity_id=opportunity.id,
            category=category,
            title=title,
            status="not_started",
        ))
