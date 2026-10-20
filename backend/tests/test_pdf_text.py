from pathlib import Path

from applify.services.pdf_text import clean_text, decode_text_file, extract_pdf_text
from tests.pdf_util import make_pdf


def test_extract_text_from_pdf(tmp_path: Path) -> None:
    path = tmp_path / "cv.pdf"
    path.write_bytes(make_pdf(["Lena Beispiel", "Erfahrung mit Vue und Python (3 Jahre)"]))
    text = extract_pdf_text(path)
    assert "Lena Beispiel" in text
    assert "Vue und Python (3 Jahre)" in text


def test_pdf_without_text_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf([]))
    assert extract_pdf_text(path) == ""


def test_broken_pdf_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4 garbage")
    assert extract_pdf_text(path) == ""


def test_decode_text_file_handles_windows_encoding() -> None:
    assert decode_text_file("Grüße".encode("cp1252")) == "Grüße"
    assert decode_text_file("﻿Grüße".encode()) == "Grüße"


def test_clean_text_collapses_blank_lines() -> None:
    assert clean_text("a  \r\n\r\n\r\n\r\nb\x00") == "a\n\nb"
