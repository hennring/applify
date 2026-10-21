from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from applify.db.models import Document
from applify.db.session import get_session
from applify.schemas.profile import ChangeItem, CvSuggestion, ProfileData
from applify.services.documents import get_document, latest_extracted_cv
from applify.services.match_store import rescore_user
from applify.services.profile_diff import apply_changes, compute_changes
from applify.services.profile_store import load_profile, normalize_profile, save_profile
from applify.services.skills import SkillTaxonomy, get_taxonomy
from applify.users import get_current_user_id

router = APIRouter(prefix="/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]
TaxonomyDep = Annotated[SkillTaxonomy, Depends(get_taxonomy)]


class CvChanges(BaseModel):
    document_id: int
    filename: str
    extracted_at: datetime | None
    changes: list[ChangeItem]
    dropped_skills: list[str]


class ApplyCvChanges(BaseModel):
    document_id: int
    change_ids: list[str]


def _suggestion(document: Document) -> CvSuggestion:
    if document.extraction_status != "done" or document.extraction_result is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Lebenslauf wurde noch nicht ausgelesen")
    return CvSuggestion.model_validate(document.extraction_result)


@router.get("")
def get_profile(session: SessionDep, user_id: UserDep) -> ProfileData:
    return load_profile(session, user_id)


@router.put("")
def put_profile(
    data: ProfileData, session: SessionDep, user_id: UserDep, taxonomy: TaxonomyDep
) -> ProfileData:
    profile = save_profile(session, user_id, normalize_profile(data, taxonomy))
    rescore_user(session, user_id)
    session.commit()
    return profile


@router.get("/cv-changes")
def get_cv_changes(
    session: SessionDep, user_id: UserDep, document_id: int | None = None
) -> CvChanges | None:
    """Proposed changes from a CV (default: the most recently extracted one)."""
    if document_id is None:
        document = latest_extracted_cv(session, user_id)
        if document is None:
            return None
    else:
        document = get_document(session, user_id, document_id)
        if document is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden")
    suggestion = _suggestion(document)
    return CvChanges(
        document_id=document.id,
        filename=document.filename,
        extracted_at=document.extracted_at,
        changes=compute_changes(load_profile(session, user_id), suggestion),
        dropped_skills=suggestion.dropped_skills,
    )


@router.post("/cv-changes/apply")
def apply_cv_changes(
    body: ApplyCvChanges, session: SessionDep, user_id: UserDep, taxonomy: TaxonomyDep
) -> ProfileData:
    document = get_document(session, user_id, body.document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden")
    updated = apply_changes(
        load_profile(session, user_id), _suggestion(document), set(body.change_ids)
    )
    profile = save_profile(session, user_id, normalize_profile(updated, taxonomy))
    rescore_user(session, user_id)
    session.commit()
    return profile
