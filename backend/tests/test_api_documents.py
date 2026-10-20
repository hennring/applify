from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import FakeLLM
from tests.pdf_util import make_pdf

CV_PDF = make_pdf(
    [
        "Lena Beispiel",
        "lena.beispiel@example.org",
        "04/2023 - heute Fullstack Developer, Pixelwerk GmbH",
        "Vue, TypeScript, Python, PostgreSQL",
    ]
)
LLM_RESULT = {
    "contact": {"name": "Lena Beispiel", "email": "lena.beispiel@example.org"},
    "roles": ["Fullstack Developer"],
    "skills": [{"name": "Vue", "evidence": "Vue, TypeScript"}],
    "experience": [
        {
            "employer": "Pixelwerk GmbH",
            "role": "Fullstack Developer",
            "start": "2023-04",
            "current": True,
        }
    ],
}


def upload(api: TestClient, doc_type: str, name: str, data: bytes) -> dict:  # type: ignore[type-arg]
    response = api.post("/api/documents", data={"type": doc_type}, files={"file": (name, data)})
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def test_upload_cv_extracts_text_and_runs_extraction(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.result = LLM_RESULT
    doc = upload(api, "cv", "Lebenslauf.pdf", CV_PDF)
    assert doc["has_text"]
    assert doc["filename"] == "Lebenslauf.pdf"
    # The task runner is synchronous in tests, so the job has finished.
    doc = api.get(f"/api/documents/{doc['id']}").json()
    assert doc["extraction_status"] == "done"
    assert "Pixelwerk GmbH" in fake_llm.calls[0]


def test_failed_extraction_is_reported(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.result = RuntimeError("Ollama weg")
    doc = upload(api, "cv", "cv.pdf", CV_PDF)
    doc = api.get(f"/api/documents/{doc['id']}").json()
    assert doc["extraction_status"] == "failed"
    assert doc["extraction_error"] == "Ollama weg"


def test_certificate_is_not_extracted(api: TestClient, fake_llm: FakeLLM) -> None:
    doc = upload(api, "certificate", "Zeugnis.pdf", CV_PDF)
    assert doc["extraction_status"] == "none"
    assert fake_llm.calls == []
    assert api.post(f"/api/documents/{doc['id']}/extract").status_code == 409


def test_scanned_cv_cannot_be_extracted(api: TestClient) -> None:
    doc = upload(api, "cv", "scan.pdf", make_pdf([]))
    assert not doc["has_text"]
    assert doc["extraction_status"] == "none"
    response = api.post(f"/api/documents/{doc['id']}/extract")
    assert response.status_code == 422
    assert "gescannt" in response.json()["detail"]


def test_sample_letter_may_be_text(api: TestClient) -> None:
    doc = upload(api, "sample_letter", "Anschreiben.txt", b"Sehr geehrte Damen")
    assert doc["content_type"] == "text/plain"
    assert doc["has_text"]


def test_rejects_non_pdf(api: TestClient) -> None:
    response = api.post("/api/documents", data={"type": "cv"}, files={"file": ("cv.txt", b"hello")})
    assert response.status_code == 422
    assert "PDF" in response.json()["detail"]


def test_list_download_and_delete(api: TestClient, tmp_path: Path) -> None:
    doc = upload(api, "certificate", "Zeugnis.pdf", CV_PDF)
    assert [d["id"] for d in api.get("/api/documents").json()] == [doc["id"]]

    file = api.get(f"/api/documents/{doc['id']}/file")
    assert file.content == CV_PDF
    assert file.headers["content-type"] == "application/pdf"
    stored = list(tmp_path.glob("1/documents/*.pdf"))
    assert len(stored) == 1

    assert api.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert api.get("/api/documents").json() == []
    assert not stored[0].exists()
    assert api.get(f"/api/documents/{doc['id']}").status_code == 404


def test_rerun_extraction(api: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.result = LLM_RESULT
    doc = upload(api, "cv", "cv.pdf", CV_PDF)
    response = api.post(f"/api/documents/{doc['id']}/extract")
    assert response.status_code == 202
    assert len(fake_llm.calls) == 2
