from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Profile, ProfileLanguage, ProfileLocation, ProfileSkill
from applify.schemas.profile import (
    Contact,
    Education,
    Language,
    Location,
    ProfileData,
    Skill,
    Station,
)
from applify.services.skills import SkillTaxonomy, match_key


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in (v.strip() for v in values):
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result


def normalize_profile(data: ProfileData, taxonomy: SkillTaxonomy) -> ProfileData:
    """Trim and dedupe lists; map skills to their canonical name where known (D12)."""
    skills: dict[str, Skill] = {}
    for skill in data.skills:
        known = taxonomy.lookup(skill.name)
        normalized = skill.model_copy(
            update={
                "name": known.name if known else skill.name.strip(),
                "canonical": known is not None,
                "category": known.category if known else None,
            }
        )
        skills.setdefault(match_key(normalized.name), normalized)
    languages: dict[str, Language] = {}
    for language in data.languages:
        languages.setdefault(language.language.strip().casefold(), language)
    return data.model_copy(
        update={
            "roles": _clean_list(data.roles),
            "skills": list(skills.values()),
            "languages": list(languages.values()),
            "exclude_keywords": _clean_list(data.exclude_keywords),
            "exclude_companies": _clean_list(data.exclude_companies),
            "preferred_companies": _clean_list(data.preferred_companies),
            "cover_letter_bullets": _clean_list(data.cover_letter_bullets),
        }
    )


def _get_row(session: Session, user_id: int) -> Profile | None:
    return session.scalar(select(Profile).where(Profile.user_id == user_id))


def load_profile(session: Session, user_id: int) -> ProfileData:
    row = _get_row(session, user_id)
    if row is None:
        return ProfileData()
    return ProfileData(
        roles=row.roles,
        seniority_years=row.seniority_years,
        salary_min=row.salary_min,
        remote_pref=row.remote_pref,
        skills=[
            Skill(
                name=s.skill,
                canonical=s.canonical,
                category=s.category,
                weight=s.weight,
                level=s.level,
                source=s.source,
            )
            for s in row.skills
        ],
        locations=[Location(name=loc.name, radius_km=loc.radius_km) for loc in row.locations],
        languages=[Language(language=lang.language, level=lang.level) for lang in row.languages],
        exclude_keywords=row.exclude_keywords,
        exclude_companies=row.exclude_companies,
        preferred_companies=row.preferred_companies,
        tone=row.tone,
        cover_letter_bullets=row.cover_letter_bullets,
        contact=Contact.model_validate(row.contact),
        experience=[Station.model_validate(s) for s in row.experience],
        education=[Education.model_validate(e) for e in row.education],
    )


def save_profile(session: Session, user_id: int, data: ProfileData) -> ProfileData:
    row = _get_row(session, user_id)
    if row is None:
        row = Profile(user_id=user_id)
        session.add(row)
    previous_locations = {loc.name.casefold(): loc for loc in row.locations}

    row.roles = data.roles
    row.seniority_years = data.seniority_years
    row.salary_min = data.salary_min
    row.remote_pref = data.remote_pref
    row.exclude_keywords = data.exclude_keywords
    row.exclude_companies = data.exclude_companies
    row.preferred_companies = data.preferred_companies
    row.tone = data.tone
    row.cover_letter_bullets = data.cover_letter_bullets
    row.contact = data.contact.model_dump()
    row.experience = [s.model_dump() for s in data.experience]
    row.education = [e.model_dump() for e in data.education]
    row.skills = [
        ProfileSkill(
            position=i,
            skill=s.name,
            canonical=s.canonical,
            category=s.category,
            weight=s.weight,
            level=s.level,
            source=s.source,
        )
        for i, s in enumerate(data.skills)
    ]
    row.locations = []
    for i, loc in enumerate(data.locations):
        # Keep coordinates (filled from GeoNames in M2) of locations that still exist.
        old = previous_locations.get(loc.name.casefold())
        row.locations.append(
            ProfileLocation(
                position=i,
                name=loc.name.strip(),
                radius_km=loc.radius_km,
                lat=old.lat if old else None,
                lon=old.lon if old else None,
            )
        )
    row.languages = [
        ProfileLanguage(position=i, language=lang.language.strip(), level=lang.level)
        for i, lang in enumerate(data.languages)
    ]
    session.flush()
    return load_profile(session, user_id)
