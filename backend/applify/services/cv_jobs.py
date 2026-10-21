import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from applify.db.models import Document
from applify.llm import LLMProvider
from applify.schemas.profile import CvSuggestion
from applify.services.cv_extraction import extract_cv
from applify.services.profile_diff import apply_changes, compute_changes
from applify.services.profile_store import load_profile, normalize_profile, save_profile
from applify.services.skills import SkillTaxonomy

log = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]


def run_cv_extraction(
    document_id: int, session_factory: SessionFactory, llm: LLMProvider, taxonomy: SkillTaxonomy
) -> None:
    """Background job: extract the CV, store the suggestion and fill the profile with it."""
    with session_factory() as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        try:
            suggestion = extract_cv(document.extracted_text or "", llm, taxonomy, date.today())
        except Exception as exc:
            log.exception("CV extraction failed for document %s", document_id)
            document.extraction_status = "failed"
            document.extraction_error = str(exc)[:2000]
        else:
            document.extraction_status = "done"
            document.extraction_error = None
            document.extraction_result = suggestion.model_dump(mode="json")
            apply_additions(session, document.user_id, suggestion, taxonomy)
        document.extracted_at = datetime.now()
        session.commit()


def apply_additions(
    session: Session, user_id: int, suggestion: CvSuggestion, taxonomy: SkillTaxonomy
) -> None:
    """Take over everything new from the CV; changes to existing values stay suggestions (F4)."""
    profile = load_profile(session, user_id)
    ids = {c.id for c in compute_changes(profile, suggestion) if c.kind == "add"}
    if ids:
        updated = apply_changes(profile, suggestion, ids)
        save_profile(session, user_id, normalize_profile(updated, taxonomy))


def fail_interrupted_jobs(session: Session) -> None:
    """Jobs run in-process (D10); after a restart, 'running' jobs will never finish."""
    session.execute(
        update(Document)
        .where(Document.extraction_status == "running")
        .values(extraction_status="failed", extraction_error="Abgebrochen durch Neustart")
    )
    session.commit()
