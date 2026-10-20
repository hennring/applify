"""Diff between the current profile and a CV suggestion (F4).

Only additions and changes are proposed, never removals, so manual edits survive a
re-extraction. Each change can be applied on its own.
"""

from applify.schemas.profile import (
    ChangeItem,
    CvSuggestion,
    Education,
    ProfileData,
    Skill,
    Station,
)
from applify.services.skills import match_key

CONTACT_FIELDS = ("name", "email", "phone", "address")


def station_key(entry: Station | Education) -> str:
    name = entry.employer if isinstance(entry, Station) else entry.institution
    return f"{name.strip().casefold()}|{entry.start or ''}"


def _station_label(s: Station) -> str:
    period = f"{s.start or '?'} – {'heute' if s.current else s.end or '?'}"
    return f"{s.role} bei {s.employer} ({period})" if s.role else f"{s.employer} ({period})"


def _education_label(e: Education) -> str:
    period = f" ({e.start or '?'} – {e.end or '?'})" if e.start or e.end else ""
    return f"{e.degree}, {e.institution}{period}" if e.degree else f"{e.institution}{period}"


def compute_changes(profile: ProfileData, suggestion: CvSuggestion) -> list[ChangeItem]:
    changes: list[ChangeItem] = []

    for key in CONTACT_FIELDS:
        current = getattr(profile.contact, key)
        suggested = getattr(suggestion.contact, key)
        if suggested and suggested != current:
            changes.append(
                ChangeItem(
                    id=f"contact:{key}",
                    field="contact",
                    kind="change" if current else "add",
                    key=key,
                    current=current or None,
                    suggested=suggested,
                )
            )

    years = suggestion.seniority_years
    if years is not None and (
        profile.seniority_years is None or abs(profile.seniority_years - years) >= 0.1
    ):
        changes.append(
            ChangeItem(
                id="seniority_years",
                field="seniority_years",
                kind="add" if profile.seniority_years is None else "change",
                current=None if profile.seniority_years is None else str(profile.seniority_years),
                suggested=str(years),
            )
        )

    roles = {r.casefold() for r in profile.roles}
    changes += [
        ChangeItem(id=f"role:{role.casefold()}", field="roles", kind="add", suggested=role)
        for role in suggestion.roles
        if role.casefold() not in roles
    ]

    skills = {match_key(s.name) for s in profile.skills}
    changes += [
        ChangeItem(
            id=f"skill:{match_key(skill.name)}", field="skills", kind="add", suggested=skill.name
        )
        for skill in suggestion.skills
        if match_key(skill.name) not in skills
    ]

    languages = {lang.language.casefold(): lang.level for lang in profile.languages}
    for language in suggestion.languages:
        current_level = languages.get(language.language.casefold())
        if current_level != language.level:
            changes.append(
                ChangeItem(
                    id=f"language:{language.language.casefold()}",
                    field="languages",
                    kind="change" if current_level else "add",
                    key=language.language,
                    current=current_level,
                    suggested=language.level,
                )
            )

    stations = {station_key(s) for s in profile.experience}
    changes += [
        ChangeItem(
            id=f"experience:{station_key(s)}",
            field="experience",
            kind="add",
            suggested=_station_label(s),
        )
        for s in suggestion.experience
        if station_key(s) not in stations
    ]

    schools = {station_key(e) for e in profile.education}
    changes += [
        ChangeItem(
            id=f"education:{station_key(e)}",
            field="education",
            kind="add",
            suggested=_education_label(e),
        )
        for e in suggestion.education
        if station_key(e) not in schools
    ]
    return changes


def apply_change(profile: ProfileData, suggestion: CvSuggestion, change: ChangeItem) -> None:
    match change.field:
        case "contact":
            assert change.key is not None
            setattr(profile.contact, change.key, change.suggested)
        case "seniority_years":
            profile.seniority_years = suggestion.seniority_years
        case "roles":
            profile.roles.append(change.suggested)
        case "skills":
            skill = next(s for s in suggestion.skills if s.name == change.suggested)
            profile.skills.append(
                # F2: CV skills start as "gern"; the user adjusts the weight.
                Skill(
                    name=skill.name,
                    canonical=skill.canonical,
                    category=skill.category,
                    weight="nice",
                    source="cv",
                )
            )
        case "languages":
            new = next(
                lang
                for lang in suggestion.languages
                if f"language:{lang.language.casefold()}" == change.id
            )
            existing = [
                lang
                for lang in profile.languages
                if lang.language.casefold() == new.language.casefold()
            ]
            if existing:
                existing[0].level = new.level
            else:
                profile.languages.append(new.model_copy())
        case "experience":
            station = next(
                s for s in suggestion.experience if f"experience:{station_key(s)}" == change.id
            )
            profile.experience.append(station.model_copy())
        case "education":
            entry = next(
                e for e in suggestion.education if f"education:{station_key(e)}" == change.id
            )
            profile.education.append(entry.model_copy())


def apply_changes(
    profile: ProfileData, suggestion: CvSuggestion, change_ids: set[str]
) -> ProfileData:
    updated = profile.model_copy(deep=True)
    for change in compute_changes(profile, suggestion):
        if change.id in change_ids:
            apply_change(updated, suggestion, change)
    updated.experience.sort(key=lambda s: s.start or "", reverse=True)
    updated.education.sort(key=lambda e: e.start or "", reverse=True)
    return updated
