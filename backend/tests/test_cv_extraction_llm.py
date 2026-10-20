"""Acceptance tests against the real local LLM (§5.4). Slow; run with `pytest -m llm`.

Values that the LLM may phrase differently are compared loosely.
"""

from datetime import date

import pytest

from applify.config import get_settings
from applify.llm.ollama import OllamaProvider
from applify.services.cv_extraction import extract_cv
from applify.services.skills import get_taxonomy
from tests.conftest import FIXTURES

pytestmark = pytest.mark.llm
TODAY = date(2026, 10, 20)


@pytest.fixture(scope="module")
def llm() -> OllamaProvider:
    settings = get_settings()
    return OllamaProvider(settings.ollama_url, settings.ollama_model, num_ctx=8192)


def test_german_fullstack_cv(llm: OllamaProvider) -> None:
    text = (FIXTURES / "cvs" / "de_fullstack.txt").read_text(encoding="utf-8")
    s = extract_cv(text, llm, get_taxonomy(), TODAY)

    assert s.contact.name == "Lena Beispiel"
    assert s.contact.email == "lena.beispiel@example.org"
    assert s.contact.phone == "+49 341 1234567"
    assert "Leipzig" in s.contact.address
    assert any("fullstack" in r.casefold() for r in s.roles)
    assert not any("praktik" in r.casefold() or "werkstud" in r.casefold() for r in s.roles)
    skills = {sk.name for sk in s.skills}
    assert {"Vue", "TypeScript", "Python", "FastAPI", "PostgreSQL", "Docker", "Pinia"} <= skills
    assert {(lang.language, lang.level) for lang in s.languages} == {
        ("Deutsch", "native"),
        ("Englisch", "C1"),
        ("Spanisch", "A2"),
    }
    assert [(st.employer.split(",")[0], st.start, st.kind) for st in s.experience] == [
        ("Pixelwerk GmbH", "2023-04", "employment"),
        ("Datenhafen AG", "2021-10", "working_student"),
        ("Stadtwerke Musterstadt", "2021-03", "internship"),
    ]
    assert s.experience[0].current
    assert s.seniority_years == 4.3
    assert any("Informatik" in e.degree for e in s.education)


def test_english_frontend_cv(llm: OllamaProvider) -> None:
    text = (FIXTURES / "cvs" / "en_frontend.txt").read_text(encoding="utf-8")
    s = extract_cv(text, llm, get_taxonomy(), TODAY)

    assert s.contact.name == "Jonas Muster"
    assert s.contact.email == "jonas.muster@example.com"
    assert s.contact.phone == "0170 9876543"
    assert any("frontend" in r.casefold() for r in s.roles)
    skills = {sk.name for sk in s.skills}
    assert {"React", "Next.js", "TypeScript", "Storybook", "Jest", "PHP", "WordPress"} <= skills
    assert {(lang.language, lang.level) for lang in s.languages} == {
        ("German", "native"),
        ("English", "C1"),
    }
    employers = [st.employer for st in s.experience]
    assert len(employers) == 2
    assert employers[0].startswith("Nordlicht Software")
    assert employers[1].startswith("Agentur Elbblick")
    assert s.seniority_years == 6.8
