import logging
import re
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

log = logging.getLogger(__name__)


def extract_pdf_text(path: Path) -> str:
    """Text of a text-based PDF via pdfplumber, pypdf as fallback (D14). No OCR."""
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        log.warning("pdfplumber failed for %s", path, exc_info=True)
    if not text.strip():
        try:
            text = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        except Exception:
            log.warning("pypdf failed for %s", path, exc_info=True)
    return clean_text(text)


def decode_text_file(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return clean_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return clean_text(data.decode("utf-8", errors="replace"))


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
