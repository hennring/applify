import uuid
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Document
from applify.services.pdf_text import decode_text_file, extract_pdf_text

DocumentType = Literal["cv", "certificate", "sample_letter"]


class UploadError(ValueError):
    pass


def detect_kind(doc_type: DocumentType, filename: str, data: bytes) -> tuple[str, str]:
    """Return (content type, file suffix). Only PDFs, plus plain text for sample letters."""
    if data.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    if doc_type == "sample_letter" and filename.lower().endswith(".txt"):
        return "text/plain", ".txt"
    allowed = "PDF oder TXT" if doc_type == "sample_letter" else "PDF"
    raise UploadError(f"Dateityp nicht unterstützt, erlaubt: {allowed}")


def store_document(
    session: Session,
    data_dir: Path,
    user_id: int,
    doc_type: DocumentType,
    filename: str,
    data: bytes,
) -> Document:
    content_type, suffix = detect_kind(doc_type, filename, data)
    relative = Path(str(user_id)) / "documents" / f"{uuid.uuid4().hex}{suffix}"
    target = data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    text = extract_pdf_text(target) if suffix == ".pdf" else decode_text_file(data)
    document = Document(
        user_id=user_id,
        type=doc_type,
        filename=Path(filename).name[:255] or f"dokument{suffix}",
        path=relative.as_posix(),
        content_type=content_type,
        size_bytes=len(data),
        extracted_text=text or None,
    )
    session.add(document)
    session.flush()
    return document


def delete_document(session: Session, data_dir: Path, document: Document) -> None:
    (data_dir / document.path).unlink(missing_ok=True)
    session.delete(document)


def get_document(session: Session, user_id: int, document_id: int) -> Document | None:
    return session.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )


def latest_extracted_cv(session: Session, user_id: int) -> Document | None:
    return session.scalar(
        select(Document)
        .where(
            Document.user_id == user_id,
            Document.type == "cv",
            Document.extraction_status == "done",
        )
        .order_by(Document.extracted_at.desc(), Document.id.desc())
        .limit(1)
    )
