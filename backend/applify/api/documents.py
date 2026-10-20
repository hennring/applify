from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.config import Settings, get_settings
from applify.db.models import Document
from applify.db.session import get_session, get_session_factory
from applify.llm import LLMProvider, get_llm
from applify.services.background import TaskRunner, get_task_runner
from applify.services.cv_jobs import SessionFactory, run_cv_extraction
from applify.services.documents import (
    DocumentType,
    UploadError,
    delete_document,
    get_document,
    store_document,
)
from applify.services.skills import SkillTaxonomy, get_taxonomy
from applify.users import get_current_user_id

router = APIRouter(prefix="/documents", tags=["documents"])

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[int, Depends(get_current_user_id)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class DocumentOut(BaseModel):
    id: int
    type: DocumentType
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    has_text: bool
    extraction_status: str
    extraction_error: str | None
    extracted_at: datetime | None

    @classmethod
    def of(cls, d: Document) -> "DocumentOut":
        return cls(
            id=d.id,
            type=d.type,
            filename=d.filename,
            content_type=d.content_type,
            size_bytes=d.size_bytes,
            uploaded_at=d.uploaded_at,
            has_text=bool(d.extracted_text),
            extraction_status=d.extraction_status,
            extraction_error=d.extraction_error,
            extracted_at=d.extracted_at,
        )


class ExtractionDeps:
    def __init__(
        self,
        runner: Annotated[TaskRunner, Depends(get_task_runner)],
        session_factory: Annotated[SessionFactory, Depends(get_session_factory)],
        llm: Annotated[LLMProvider, Depends(get_llm)],
        taxonomy: Annotated[SkillTaxonomy, Depends(get_taxonomy)],
    ) -> None:
        self.runner = runner
        self.session_factory = session_factory
        self.llm = llm
        self.taxonomy = taxonomy

    def start(self, session: Session, document: Document) -> None:
        document.extraction_status = "running"
        document.extraction_error = None
        session.commit()
        self.runner(run_cv_extraction, document.id, self.session_factory, self.llm, self.taxonomy)


ExtractionDep = Annotated[ExtractionDeps, Depends()]


def _get_or_404(session: Session, user_id: int, document_id: int) -> Document:
    document = get_document(session, user_id, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden")
    return document


@router.get("")
def list_documents(session: SessionDep, user_id: UserDep) -> list[DocumentOut]:
    documents = session.scalars(
        select(Document).where(Document.user_id == user_id).order_by(Document.uploaded_at.desc())
    )
    return [DocumentOut.of(d) for d in documents]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    type: Annotated[DocumentType, Form()],
    file: UploadFile,
    session: SessionDep,
    user_id: UserDep,
    settings: SettingsDep,
    extraction: ExtractionDep,
) -> DocumentOut:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"Datei größer als {settings.max_upload_mb} MB"
        )
    try:
        document = store_document(
            session, settings.data_dir, user_id, type, file.filename or "", data
        )
    except UploadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    session.commit()
    # F2: a new CV is read right away.
    if document.type == "cv" and document.extracted_text:
        extraction.start(session, document)
    return DocumentOut.of(document)


@router.get("/{document_id}")
def get_document_info(document_id: int, session: SessionDep, user_id: UserDep) -> DocumentOut:
    return DocumentOut.of(_get_or_404(session, user_id, document_id))


@router.get("/{document_id}/file", response_class=FileResponse)
def download_document(
    document_id: int, session: SessionDep, user_id: UserDep, settings: SettingsDep
) -> FileResponse:
    document = _get_or_404(session, user_id, document_id)
    return FileResponse(
        settings.data_dir / document.path,
        media_type=document.content_type,
        filename=document.filename,
        content_disposition_type="inline",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int, session: SessionDep, user_id: UserDep, settings: SettingsDep
) -> None:
    delete_document(session, settings.data_dir, _get_or_404(session, user_id, document_id))
    session.commit()


@router.post("/{document_id}/extract", status_code=status.HTTP_202_ACCEPTED)
def extract_document(
    document_id: int, session: SessionDep, user_id: UserDep, extraction: ExtractionDep
) -> DocumentOut:
    document = _get_or_404(session, user_id, document_id)
    if document.type != "cv":
        raise HTTPException(status.HTTP_409_CONFLICT, "Nur Lebensläufe werden ausgelesen")
    if not document.extracted_text:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Kein Text im PDF gefunden – vermutlich gescannt. Bitte ein Text-PDF hochladen.",
        )
    if document.extraction_status == "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "Wird bereits ausgelesen")
    extraction.start(session, document)
    return DocumentOut.of(document)
