"""Matching (§5.3): hard filters and a deterministic soft score with explanation (D1, N5).

Pure functions: a job and a profile in, score, exclusion reason and breakdown out.
Unknown components drop out of the weighting instead of counting as zero (F13); unknown
skills count as neutral instead, since they carry the most weight.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from applify.schemas.profile import LanguageLevel, ProfileData, Skill
from applify.services.geo import distance_km
from applify.services.normalize import normalize_company, normalize_title
from applify.services.skills import SkillTaxonomy, alias_pattern, match_key, mentions

WEIGHTS = {"skills": 45, "role": 20, "seniority": 15, "location": 10, "salary": 10}
LABELS = {
    "skills": "Skills",
    "role": "Rolle/Titel",
    "seniority": "Seniorität",
    "location": "Ort/Remote",
    "salary": "Gehalt",
}
# Three wanted skills in a posting already give full points for coverage ("reach").
SKILL_TARGET = 3.0
# Skill value = share of the asked technologies the profile covers (counts most) and how
# many wanted skills the posting names; each skill marked "avoid" costs a fixed amount.
SHARE_WEIGHT = 0.6
AVOID_PENALTY = 0.35
# Skill value of a posting that names no technologies (or only short info).
NEUTRAL_SKILLS = 0.5
# How much an asked technology outside the profile weighs against the hits, per category.
# Tools, methods and design rarely decide whether a job fits.
FOREIGN_WEIGHT = {
    "tool": 0.0,
    "methodology": 0.0,
    "design": 0.0,
    "cloud": 0.5,
    "devops": 0.5,
    "testing": 0.5,
}

EvidenceKind = Literal["hit", "miss", "unknown"]


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    text: str


@dataclass
class Component:
    key: str
    value: float | None  # 0..1, None = unknown
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class JobFacts:
    title: str
    company: str
    description: str
    skills: tuple[str, ...]
    lat: float | None
    lon: float | None
    remote_type: str | None
    salary_min: int | None
    salary_max: int | None
    has_full_text: bool


@dataclass(frozen=True)
class ProfilePlace:
    name: str
    lat: float
    lon: float
    radius_km: int


@dataclass
class MatchResult:
    score: int
    excluded_reason: str | None
    components: list[Component]
    low_data: bool

    def breakdown(self) -> dict[str, Any]:
        known = sum(WEIGHTS[c.key] for c in self.components if c.value is not None)
        return {
            "low_data": self.low_data,
            "components": [
                {
                    "key": c.key,
                    "label": LABELS[c.key],
                    "weight": WEIGHTS[c.key],
                    "value": None if c.value is None else round(c.value, 3),
                    # Points after renormalization, so they add up to the score.
                    "points": None
                    if c.value is None or not known
                    else round(100 * WEIGHTS[c.key] * c.value / known, 1),
                    "evidence": [{"kind": e.kind, "text": e.text} for e in c.evidence],
                }
                for c in self.components
            ],
        }


def _num(value: float) -> str:
    return (
        f"{value:,.1f}".rstrip("0")
        .rstrip(".")
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _euro(value: int) -> str:
    return f"{value:,} €".replace(",", ".")


def _skill_in(text: str, skill: Skill, taxonomy: SkillTaxonomy) -> bool:
    known = taxonomy.lookup(skill.name)
    aliases = (known.name, *known.synonyms) if known else (skill.name,)
    return any(alias_pattern(alias).search(text) for alias in aliases)


# --- hard filters ---------------------------------------------------------------------

LEVEL_ORDER: list[LanguageLevel] = ["A1", "A2", "B1", "B2", "C1", "C2", "native"]
LANGUAGES = {
    "Englisch": r"englisch\w*|english",
    "Deutsch": r"deutsch\w*|german",
    "Französisch": r"französisch\w*|french",
    "Spanisch": r"spanisch\w*|spanish",
    "Italienisch": r"italienisch\w*|italian",
    "Niederländisch": r"niederländisch\w*|dutch",
    "Polnisch": r"polnisch\w*|polish",
    "Tschechisch": r"tschechisch\w*|czech",
    "Russisch": r"russisch\w*|russian",
    "Chinesisch": r"chinesisch\w*|mandarin|chinese",
    "Japanisch": r"japanisch\w*|japanese",
    "Arabisch": r"arabisch\w*|arabic",
    "Türkisch": r"türkisch\w*|turkish",
}
# Wording → minimal level; "fließend" is used loosely in postings, so it counts as B2.
REQUIRED_LEVEL: list[tuple[str, LanguageLevel]] = [
    (r"muttersprach\w*|native|c2", "C2"),
    (r"verhandlungssicher\w*|business[\s-]fluent|c1", "C1"),
    (r"fließend\w*|fluent", "B2"),
]
LANGUAGE_RE = re.compile(
    "|".join(rf"(?P<l{i}>\b(?:{p})\b)" for i, p in enumerate(LANGUAGES.values())), re.IGNORECASE
)
LEVEL_RE = re.compile(
    "|".join(rf"(?P<v{i}>\b(?:{p})\b)" for i, (p, _) in enumerate(REQUIRED_LEVEL)), re.IGNORECASE
)
# A level belongs to a language only if nothing like "und" or a comma lies between them,
# so in "Deutsch (C1) und gute Englischkenntnisse" the C1 is for German.
SEPARATOR = re.compile(r"[.,;\n]|\b(und|sowie|oder|and|or)\b", re.IGNORECASE)
MAX_GAP = 40


def required_languages(text: str) -> dict[str, LanguageLevel]:
    """Languages a posting explicitly demands with a level (only clear wording counts)."""
    names = list(LANGUAGES)
    languages = [
        (m.start(), m.end(), names[int(next(k for k, v in m.groupdict().items() if v)[1:])])
        for m in LANGUAGE_RE.finditer(text)
    ]
    found: dict[str, LanguageLevel] = {}
    for m in LEVEL_RE.finditer(text):
        level = REQUIRED_LEVEL[int(next(k for k, v in m.groupdict().items() if v)[1:])][1]
        before = [lang for lang in languages if lang[1] <= m.start()]
        after = [lang for lang in languages if lang[0] >= m.end()]
        candidates = [
            *([(text[before[-1][1] : m.start()], before[-1][2])] if before else []),
            *([(text[m.end() : after[0][0]], after[0][2])] if after else []),
        ]
        for gap, language in candidates:
            if len(gap) <= MAX_GAP and not SEPARATOR.search(gap):
                if LEVEL_ORDER.index(level) > LEVEL_ORDER.index(found.get(language, "A1")):
                    found[language] = level
                break
    return found


def _language_gap(job: JobFacts, profile: ProfileData) -> str | None:
    have = {lang.language.casefold(): lang.level for lang in profile.languages}
    for language, level in required_languages(f"{job.title}\n{job.description}").items():
        own = have.get(language.casefold())
        # C2 and "native" are treated alike.
        needed = LEVEL_ORDER.index(level)
        if own is None or LEVEL_ORDER.index(own) < min(needed, LEVEL_ORDER.index("C2")):
            return f"Gefordert: {language} ({'Muttersprache/C2' if level == 'C2' else level})"
    return None


def _nearest(job: JobFacts, places: list[ProfilePlace]) -> tuple[ProfilePlace, float] | None:
    if job.lat is None or job.lon is None or not places:
        return None
    lat, lon = job.lat, job.lon
    return min(
        ((p, distance_km(lat, lon, p.lat, p.lon)) for p in places),
        key=lambda pd: pd[1] - pd[0].radius_km,
    )


def _remote_ok(job: JobFacts, profile: ProfileData) -> bool:
    return job.remote_type == "remote" and profile.remote_pref == "remote"


def hard_filter(
    job: JobFacts, profile: ProfileData, places: list[ProfilePlace], taxonomy: SkillTaxonomy
) -> str | None:
    """Reason why the job is hidden, or None."""
    text = f"{job.title}\n{job.description}"
    for keyword in profile.exclude_keywords:
        # Left word boundary only, so "Zeitarbeit" also hides "Zeitarbeitsfirma".
        if re.search(rf"(?<!\w){re.escape(keyword)}", text, re.IGNORECASE):
            return f"Ausschlusswort „{keyword}“"
    company = normalize_company(job.company)
    for excluded in profile.exclude_companies:
        name = normalize_company(excluded)
        if name and (company == name or company.startswith(f"{name} ")):
            return f"Ausgeschlossene Firma „{excluded}“"
    nearest = _nearest(job, places)
    if nearest and nearest[1] > nearest[0].radius_km and not _remote_ok(job, profile):
        place, distance = nearest
        return f"Außerhalb aller Radien ({round(distance)} km bis {place.name})"
    if job.salary_max is not None and profile.salary_min and job.salary_max < profile.salary_min:
        return f"Gehalt bis {_euro(job.salary_max)} unter {_euro(profile.salary_min)}"
    if gap := _language_gap(job, profile):
        return gap
    for skill in profile.skills:
        if skill.weight == "avoid" and _skill_in(job.title, skill, taxonomy):
            return f"„{skill.name}“ ist Kernanforderung (Titel)"
    return None


# --- soft score -----------------------------------------------------------------------


def score_skills(job: JobFacts, profile: ProfileData, taxonomy: SkillTaxonomy) -> Component:
    """How well the technologies a posting asks for fit the profile.

    A posting that names no technologies says nothing about the fit, so the component is
    neutral (half the points) rather than zero. Otherwise the share of the asked
    technologies the profile covers counts most; core technologies outside the profile pull
    it down, generic ones (tools, methods, design) do not.
    """
    wanted = [s for s in profile.skills if s.weight in ("must", "nice")]
    avoid = [s for s in profile.skills if s.weight == "avoid"]
    if not wanted:
        return Component("skills", None, [Evidence("unknown", "Keine Skills im Profil")])
    text = f"{job.title}\n{job.description}"
    in_job = {name.casefold() for name in job.skills}

    def found(skill: Skill) -> bool:
        known = taxonomy.lookup(skill.name)
        return known.name.casefold() in in_job if known else mentions(skill.name, text)

    must = [s.name for s in wanted if s.weight == "must" and found(s)]
    nice = [s.name for s in wanted if s.weight == "nice" and found(s)]
    bad = [s.name for s in avoid if found(s)]
    own = {match_key(s.name) for s in profile.skills}
    foreign: list[tuple[str, float]] = []
    generic: list[str] = []
    for name in job.skills:
        if match_key(name) in own:
            continue
        known = taxonomy.lookup(name)
        weight = FOREIGN_WEIGHT.get(known.category if known else "", 1.0)
        (foreign.append((name, weight)) if weight else generic.append(name))

    if not (must or nice or bad or foreign):
        # Nothing known about the asked technologies: neither a reason to rank down nor up.
        # Counted as half the points rather than left out: skills weigh most, so without
        # them a matching title and place alone would reach 100.
        if not job.has_full_text:
            return Component(
                "skills",
                NEUTRAL_SKILLS,
                [Evidence("unknown", "Keine Skills erkennbar (Kurzinfo) – neutral bewertet")],
            )
        evidence = [Evidence("unknown", "Keine konkreten Technologien genannt – neutral bewertet")]
        if generic:
            evidence.append(Evidence("unknown", "Allgemein: " + ", ".join(generic[:6])))
        return Component("skills", NEUTRAL_SKILLS, evidence)

    evidence = [Evidence("hit", f"{name} (Pflicht)") for name in must]
    evidence += [Evidence("hit", f"{name} (gern)") for name in nice]
    evidence += [Evidence("miss", f"{name} (will ich nicht)") for name in bad]
    if foreign:
        names = ", ".join(name for name, _ in foreign[:6])
        evidence.append(Evidence("miss", f"Nicht in deinem Profil: {names}"))
    if generic:
        evidence.append(Evidence("unknown", "Allgemein: " + ", ".join(generic[:6])))

    hits = len(must) + 0.5 * len(nice)
    other = sum(weight for _, weight in foreign)
    share = hits / (hits + other) if hits + other else 0.0
    target = min(SKILL_TARGET, sum(1.0 if s.weight == "must" else 0.5 for s in wanted))
    reach = min(1.0, hits / target)
    value = SHARE_WEIGHT * share + (1 - SHARE_WEIGHT) * reach - AVOID_PENALTY * len(bad)
    return Component("skills", max(0.0, min(1.0, value)), evidence)


# Role words with the same meaning; compounds are split ("Webentwickler" → web entwickler).
ROLE_SYNONYMS = {
    "developer": "entwickler",
    "engineer": "entwickler",
    "programmierer": "entwickler",
    "softwareingenieur": "software entwickler",
    "dev": "entwickler",
}
ROLE_SUFFIXES = re.compile(
    r"(?<=\w)(entwickler|engineer|ingenieur|architekt|administrator|berater)\b"
)
ROLE_STOPWORDS = frozenset(
    [
        "m",
        "w",
        "d",
        "f",
        "x",
        "in",
        "im",
        "fur",
        "und",
        "der",
        "die",
        "das",
        "mit",
        "bei",
        "als",
        "ab",
        "zum",
        "zur",
        "am",
        "an",
        "senior",
        "junior",
        "lead",
        "sr",
        "jr",
        "remote",
        "hybrid",
        "vollzeit",
        "teilzeit",
    ]
)


def role_tokens(title: str) -> set[str]:
    text = normalize_title(title)
    text = re.sub(r"\b(full|front|back)\s+(stack|end)\b", r"\1\2", text)
    text = ROLE_SUFFIXES.sub(r" \1", text)
    words = " ".join(ROLE_SYNONYMS.get(w, w) for w in text.split()).split()
    return {w for w in words if w not in ROLE_STOPWORDS and len(w) > 1}


def score_role(job: JobFacts, profile: ProfileData) -> Component:
    if not profile.roles:
        return Component("role", None, [Evidence("unknown", "Keine Wunschrollen im Profil")])
    title = role_tokens(job.title)
    best_role, best = "", 0.0
    for role in profile.roles:
        tokens = role_tokens(role)
        overlap = len(tokens & title) / len(tokens) if tokens else 0.0
        if overlap > best:
            best_role, best = role, overlap
    if best >= 0.99:
        return Component("role", 1.0, [Evidence("hit", f"Passt zu „{best_role}“")])
    if best > 0:
        return Component("role", best, [Evidence("hit", f"Teilweise wie „{best_role}“")])
    return Component("role", 0.0, [Evidence("miss", "Keine Wunschrolle im Titel")])


SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|head of|leiter\w*|teamlead\w*|architekt\w*|architect)\b",
    re.IGNORECASE,
)
JUNIOR_TITLE = re.compile(
    r"\b(junior|jr\.?|einsteiger\w*|berufseinsteiger\w*|trainee|graduate|absolvent\w*|"
    r"young professional)\b",
    re.IGNORECASE,
)
YEARS_REQUIRED = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:jahre|years)\b[^.\n]{0,40}?"
    r"(?:erfahrung|experience)",
    re.IGNORECASE,
)


def score_seniority(job: JobFacts, profile: ProfileData) -> Component:
    years = profile.seniority_years
    if years is None:
        return Component("seniority", None, [Evidence("unknown", "Berufserfahrung unbekannt")])
    own = _num(years)
    values: list[tuple[float, Evidence]] = []
    if SENIOR_TITLE.search(job.title):
        value = 1.0 if years >= 5 else 0.5 if years >= 3 else 0.2
        kind: EvidenceKind = "hit" if value == 1.0 else "miss"
        values.append((value, Evidence(kind, f"Senior-Stelle, du: {own} Jahre")))
    elif JUNIOR_TITLE.search(job.title):
        value = 1.0 if years <= 4 else 0.7
        values.append((value, Evidence("hit" if value == 1.0 else "miss", "Junior-Stelle")))
    required = [int(m[1]) for m in YEARS_REQUIRED.finditer(job.description) if int(m[1]) <= 15]
    if required:
        needed = max(required)
        value = 1.0 if years >= needed else max(0.0, 1 - (needed - years) / 3)
        kind = "hit" if value == 1.0 else "miss"
        values.append((value, Evidence(kind, f"Fordert {needed} Jahre, du: {own}")))
    if not values:
        return Component("seniority", None, [Evidence("unknown", "Keine Angabe zur Seniorität")])
    return Component("seniority", min(v for v, _ in values), [e for _, e in values])


def score_location(job: JobFacts, profile: ProfileData, places: list[ProfilePlace]) -> Component:
    if job.remote_type == "remote":
        if profile.remote_pref == "remote":
            return Component("location", 1.0, [Evidence("hit", "Voll remote")])
        if profile.remote_pref == "no":
            return Component("location", 0.5, [Evidence("miss", "Voll remote, du willst vor Ort")])
    nearest = _nearest(job, places)
    if nearest is None:
        return Component("location", None, [Evidence("unknown", "Ort unbekannt")])
    place, distance = nearest
    if distance > place.radius_km:
        # Only reached for remote jobs; others are hidden by the hard filter.
        return Component("location", 0.8, [Evidence("hit", "Remote, Ort außerhalb des Radius")])
    value = 1 - 0.5 * distance / max(place.radius_km, 1)
    evidence = [Evidence("hit", f"{round(distance)} km bis {place.name}")]
    if job.remote_type == "hybrid" and profile.remote_pref in ("hybrid", "remote"):
        value = min(1.0, value + 0.2)
        evidence.append(Evidence("hit", "Hybrid möglich"))
    return Component("location", value, evidence)


def score_salary(job: JobFacts, profile: ProfileData) -> Component:
    if not profile.salary_min:
        return Component("salary", None, [Evidence("unknown", "Kein Mindestgehalt im Profil")])
    top = job.salary_max if job.salary_max is not None else job.salary_min
    if top is None:
        return Component("salary", None, [Evidence("unknown", "Gehalt unbekannt")])
    shown = (
        f"{_euro(job.salary_min)} – {_euro(job.salary_max)}"
        if job.salary_min is not None and job.salary_max is not None
        else _euro(top)
    )
    if top >= profile.salary_min:
        return Component("salary", 1.0, [Evidence("hit", shown)])
    if top >= 0.9 * profile.salary_min:
        return Component("salary", 0.5, [Evidence("miss", f"{shown}, knapp unter Minimum")])
    return Component("salary", 0.0, [Evidence("miss", f"{shown}, unter Minimum")])


def match_job(
    job: JobFacts, profile: ProfileData, places: list[ProfilePlace], taxonomy: SkillTaxonomy
) -> MatchResult:
    components = [
        score_skills(job, profile, taxonomy),
        score_role(job, profile),
        score_seniority(job, profile),
        score_location(job, profile, places),
        score_salary(job, profile),
    ]
    known = [(WEIGHTS[c.key], c.value) for c in components if c.value is not None]
    total = sum(w for w, _ in known)
    score = round(100 * sum(w * v for w, v in known) / total) if total else 0
    return MatchResult(
        score=score,
        excluded_reason=hard_filter(job, profile, places, taxonomy),
        components=components,
        low_data=not job.has_full_text,
    )
