from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Job, Profile, ProfileSkill
from applify.services.skills import SKILLS_FILE
from applify.services.taxonomy_sync import STATE_FILE, sync_taxonomy, taxonomy_digest


def skill(position: int, name: str, category: str | None) -> ProfileSkill:
    return ProfileSkill(
        position=position,
        skill=name,
        canonical=category is not None,
        category=category,
        weight="must",
        source="user",
    )


def test_changed_taxonomy_reclassifies_profiles_and_rescans_jobs(
    db_session: Session, tmp_path: Path
) -> None:
    profile = Profile(
        user_id=1,
        skills=[
            skill(0, "Machine Learning", "data"),  # moved to its own category
            skill(1, "pytorch", None),  # newly known
            skill(2, "PyTorch", None),  # the same skill twice once canonical
            skill(3, "Basteln", "tool"),
        ],
    )
    job = Job(
        title="ML Engineer",
        company="Acme",
        description="PyTorch",
        company_norm="acme",
        title_norm="ml engineer",
        fingerprint="y" * 40,
        skills=[],
    )
    db_session.add_all([profile, job])
    db_session.flush()

    assert sync_taxonomy(db_session, tmp_path) is True
    rows = db_session.scalars(
        select(ProfileSkill).where(ProfileSkill.profile_id == profile.id)
    ).all()
    assert sorted((r.skill, r.category, r.canonical) for r in rows) == [
        ("Basteln", None, False),
        ("Machine Learning", "ai", True),
        ("PyTorch", "ai", True),
    ]
    db_session.refresh(job)
    assert job.skills is None  # scanned again with the next rating
    assert (tmp_path / STATE_FILE).read_text(encoding="utf-8") == taxonomy_digest()


def test_unchanged_taxonomy_is_left_alone(db_session: Session, tmp_path: Path) -> None:
    (tmp_path / STATE_FILE).write_text(taxonomy_digest(SKILLS_FILE), encoding="utf-8")
    assert sync_taxonomy(db_session, tmp_path) is False
