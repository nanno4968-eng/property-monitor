import shutil
from pathlib import Path

from sqlalchemy import select

from app.db import session_scope
from app.models import DueDiligenceItem, Opportunity, RawDocument, RiskFlag, Score
from app.pipeline import run_pipeline
from app.services.due_diligence import DEFAULT_CHECKLIST

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "sample_sheriff_notice.txt"


def test_pipeline_creates_opportunity_from_sample_notice(clean_db, clean_inbox):
    shutil.copy(SAMPLE_PATH, clean_inbox / "notice1.txt")

    summary = run_pipeline()

    assert summary["new_opportunities"] == 1
    assert summary["documents_processed"] == 1

    with session_scope() as session:
        opp = session.execute(select(Opportunity)).scalar_one()
        assert "1234" in opp.title
        assert opp.case_number == "12345/2026"
        assert opp.reserve_price == 850000

        risk_flags = session.execute(select(RiskFlag).where(RiskFlag.opportunity_id == opp.id)).scalars().all()
        assert len(risk_flags) >= 2  # at minimum occupation_status_unknown + title verification

        score = session.execute(select(Score).where(Score.opportunity_id == opp.id)).scalar_one()
        assert 0 <= score.opportunity_score <= 100
        assert 0 <= score.risk_score <= 100
        assert 0 <= score.completeness_score <= 100

        checklist = session.execute(
            select(DueDiligenceItem).where(DueDiligenceItem.opportunity_id == opp.id)
        ).scalars().all()
        assert len(checklist) == len(DEFAULT_CHECKLIST)

        raw_doc = session.execute(select(RawDocument)).scalar_one()
        assert raw_doc.processing_status == "processed"


def test_reprocessing_same_file_is_a_noop(clean_db, clean_inbox):
    shutil.copy(SAMPLE_PATH, clean_inbox / "notice1.txt")
    run_pipeline()

    # The collector moves processed files out of the inbox, so a second run
    # with an empty inbox should find nothing to do.
    summary = run_pipeline()
    assert summary["documents_processed"] == 0
    assert summary["new_opportunities"] == 0

    with session_scope() as session:
        assert len(session.execute(select(Opportunity)).scalars().all()) == 1


def test_near_duplicate_notice_merges_into_existing_opportunity(clean_db, clean_inbox):
    shutil.copy(SAMPLE_PATH, clean_inbox / "notice1.txt")
    run_pipeline()

    # Same case number, erf, township, auction date, reserve price and sheriff -
    # different file content (and therefore a different checksum) so the
    # collector doesn't just skip it outright.
    variant_text = SAMPLE_PATH.read_text() + "\n\nRe-advertised for the convenience of bidders.\n"
    (clean_inbox / "notice1_reissued.txt").write_text(variant_text)

    summary = run_pipeline()

    assert summary["documents_processed"] == 1
    assert summary["updated_opportunities"] == 1
    assert summary["new_opportunities"] == 0

    with session_scope() as session:
        opportunities = session.execute(select(Opportunity)).scalars().all()
        assert len(opportunities) == 1  # merged, not duplicated
        assert len(opportunities[0].source_listings) == 2  # both documents preserved
