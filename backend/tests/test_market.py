import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from applify.db.models import Job
from applify.services import market
from applify.services.skills import SKILLS_FILE, get_taxonomy


def test_dashboard_waits_for_the_pipeline(api: TestClient) -> None:
    # The test database has no marts: the analytics pipeline never ran there.
    assert api.get("/api/market").json()["available"] is False


@pytest.fixture
def skills_file(tmp_path: Path) -> Iterator[Path]:
    copy = tmp_path / "skills.yaml"
    shutil.copy(SKILLS_FILE, copy)
    yield copy
    get_taxonomy.cache_clear()


def job(description: str) -> Job:
    return Job(
        title="Data Engineer",
        company="Acme",
        description=description,
        company_norm="acme",
        title_norm="data engineer",
        fingerprint="x" * 40,
        skills=["Python"],
    )


def test_accepted_candidate_joins_the_taxonomy(db_session: Session, skills_file: Path) -> None:
    named, other = job("Wir nutzen Snowflake und Python."), job("Nur Python.")
    db_session.add_all([named, other])
    db_session.flush()

    touched = market.accept_candidate(db_session, " Snowflake ", "data", skills_file=skills_file)

    assert touched == 1
    assert skills_file.read_text(encoding="utf-8").endswith(
        '# --- Added from the market analysis ---\n- {name: "Snowflake", category: data}\n'
    )
    # Rescanned with the next rating; the other job keeps its skills.
    db_session.refresh(named)
    db_session.refresh(other)
    assert named.skills is None
    assert other.skills == ["Python"]


@pytest.mark.parametrize(
    ("name", "category", "message"),
    [
        ("Python", "language", "schon in der Taxonomie"),
        ("Snowflake", "warehouse", "Unbekannte Kategorie"),
        ("<script>", "data", "Ungültiger Name"),
    ],
)
def test_invalid_candidates_are_refused(
    db_session: Session, skills_file: Path, name: str, category: str, message: str
) -> None:
    before = skills_file.read_text(encoding="utf-8")
    with pytest.raises(market.CandidateError, match=message):
        market.accept_candidate(db_session, name, category, skills_file=skills_file)
    assert skills_file.read_text(encoding="utf-8") == before
