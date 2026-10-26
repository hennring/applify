"""Bring stored data in line with skills.yaml after it changed (D12).

Profiles store the category of each skill, and jobs store the skills found in their text;
both are derived from the taxonomy and go stale when an entry moves or a skill is added.
"""

import hashlib
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from applify.db.models import Job, Profile, ProfileSkill
from applify.services.match_store import rescore_user
from applify.services.skills import SKILLS_FILE, SkillTaxonomy, get_taxonomy, match_key

STATE_FILE = "taxonomy.sha256"


def taxonomy_digest(skills_file: Path = SKILLS_FILE) -> str:
    # Line endings depend on the git checkout, not on the content.
    return hashlib.sha256(skills_file.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sync_taxonomy(session: Session, data_dir: Path, *, skills_file: Path = SKILLS_FILE) -> bool:
    """Reclassify profile skills and rescan jobs if skills.yaml changed since the last sync."""
    state = data_dir / STATE_FILE
    digest = taxonomy_digest(skills_file)
    if state.is_file() and state.read_text(encoding="utf-8").strip() == digest:
        return False
    reclassify_profile_skills(session, get_taxonomy())
    session.execute(update(Job).values(skills=None))  # rescanned by the scoring below
    for user_id in session.scalars(select(Profile.user_id)):
        rescore_user(session, user_id)
    session.commit()
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(digest, encoding="utf-8")
    return True


def reclassify_profile_skills(session: Session, taxonomy: SkillTaxonomy) -> None:
    """Canonical name and category from the taxonomy; a skill named twice is kept once."""
    seen: set[tuple[int, str]] = set()
    rows = session.scalars(
        select(ProfileSkill).order_by(ProfileSkill.profile_id, ProfileSkill.position)
    )
    for row in rows:
        known = taxonomy.lookup(row.skill)
        if known is not None:
            row.skill, row.canonical, row.category = known.name, True, known.category
        else:
            row.canonical, row.category = False, None
        key = (row.profile_id, match_key(row.skill))
        if key in seen:
            session.delete(row)
        seen.add(key)
    session.flush()
