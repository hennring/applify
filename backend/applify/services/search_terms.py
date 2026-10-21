"""Search terms from the profile (§5.1): roles plus "role + top must skill"."""

import re

from applify.schemas.profile import ProfileData
from applify.services.normalize import clean_title

MAX_TERMS = 8
TOP_SKILLS = 2
# Generic job words; what remains is the core of a role ("Fullstack Developer" → "Fullstack").
GENERIC_WORDS = re.compile(
    r"\b(developer|entwickler(in)?|engineer|ingenieur(in)?|programmierer(in)?|"
    r"consultant|berater(in)?|specialist|spezialist(in)?)\b",
    re.IGNORECASE,
)
# Most German postings use the German word.
GERMAN = {"developer": "Entwickler"}


def _core(role: str) -> str:
    return re.sub(r"\s+", " ", GENERIC_WORDS.sub(" ", role)).strip(" -/")


def _german(role: str) -> str:
    return re.sub(
        r"\b(" + "|".join(GERMAN) + r")\b",
        lambda m: GERMAN[m.group().casefold()],
        role,
        flags=re.IGNORECASE,
    )


def derive_search_terms(profile: ProfileData, limit: int = MAX_TERMS) -> list[str]:
    roles = [clean_title(r) for r in profile.roles if clean_title(r)]
    skills = [s.name for s in profile.skills if s.weight == "must"][:TOP_SKILLS]

    candidates = [*roles, *(_german(r) for r in roles)]
    cores = [c for c in dict.fromkeys(_core(r) for r in roles) if c]
    # No "Java Java" from "Java Entwickler" + Java.
    candidates += [
        f"{core} {skill}"
        for skill in skills
        for core in cores
        if skill.casefold() not in core.casefold().split()
    ]
    if not roles:
        candidates += skills

    terms: dict[str, str] = {}
    for term in candidates:
        terms.setdefault(term.casefold(), term)
    return list(terms.values())[:limit]
