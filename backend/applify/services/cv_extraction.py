"""CV -> LLM -> validated profile suggestion (§5.4).

The LLM only reads the CV. Everything that can be checked or computed is done in code:
skills need evidence in the original text and are normalized to skills.yaml, email and
phone are cross-checked against the text, language levels are mapped to CEFR and the
years of experience are computed from the stations.
"""

import re
from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, Field

from applify.llm import LLMProvider, load_prompt
from applify.schemas.profile import (
    Contact,
    CvSuggestion,
    Education,
    Language,
    LanguageLevel,
    Station,
    StationKind,
    SuggestedSkill,
)
from applify.services.skills import SkillTaxonomy, match_key, mentions

PROMPT = "cv_extraction_v1"
MAX_CV_CHARS = 20_000
MAX_ROLES = 5


# --- Schema the LLM fills (D5). Deliberately loose; validation happens below. ---


class LlmContact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class LlmSkill(BaseModel):
    name: str
    evidence: str = Field(description="Verbatim quote from the CV, max. 80 characters")


class LlmLanguage(BaseModel):
    language: str
    level: str = Field(description="Level as written in the CV")


class LlmStation(BaseModel):
    employer: str
    role: str = ""
    start: str | None = Field(default=None, description="YYYY-MM")
    end: str | None = Field(default=None, description="YYYY-MM, null if current")
    current: bool = False


class LlmEducation(BaseModel):
    institution: str
    degree: str = ""
    start: str | None = Field(default=None, description="YYYY-MM")
    end: str | None = Field(default=None, description="YYYY-MM")


class CvExtraction(BaseModel):
    contact: LlmContact = LlmContact()
    roles: list[str] = []
    skills: list[LlmSkill] = []
    languages: list[LlmLanguage] = []
    experience: list[LlmStation] = []
    education: list[LlmEducation] = []


# --- Pipeline ---


def extract_cv(text: str, llm: LLMProvider, taxonomy: SkillTaxonomy, today: date) -> CvSuggestion:
    raw = llm.generate_structured(
        f"CV:\n\n{text[:MAX_CV_CHARS]}", CvExtraction, system=load_prompt(PROMPT)
    )
    return normalize(raw, text, taxonomy, today)


def normalize(raw: CvExtraction, text: str, taxonomy: SkillTaxonomy, today: date) -> CvSuggestion:
    skills, dropped = normalize_skills(raw.skills, text, taxonomy)
    experience = [
        Station(
            employer=s.employer.strip(),
            role=s.role.strip(),
            kind=classify_station(s.role),
            start=parse_month(s.start, end=False),
            end=None if s.current else parse_month(s.end, end=True),
            current=s.current,
        )
        for s in raw.experience
        if s.employer.strip()
    ]
    return CvSuggestion(
        contact=normalize_contact(raw.contact, text),
        roles=dedupe(r.strip() for r in raw.roles if classify_station(r) == "employment")[
            :MAX_ROLES
        ],
        skills=skills,
        dropped_skills=dropped,
        languages=normalize_languages(raw.languages),
        experience=experience,
        education=[
            Education(
                institution=e.institution.strip(),
                degree=e.degree.strip(),
                start=parse_month(e.start, end=False),
                end=parse_month(e.end, end=True),
            )
            for e in raw.education
            if e.institution.strip()
        ],
        seniority_years=experience_years(experience, today),
    )


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result


# --- Skills ---


def normalize_skills(
    raw: list[LlmSkill], text: str, taxonomy: SkillTaxonomy
) -> tuple[list[SuggestedSkill], list[str]]:
    """Merge the LLM's skills with a deterministic scan of the text for known skills.

    A skill is only kept if one of its names actually appears in the CV text; an evidence
    quote alone is not enough, because it may be real text that names a different skill.
    """
    skills: dict[str, SuggestedSkill] = {}
    dropped: list[str] = []
    for item in raw:
        name = item.name.strip()
        if not name or len(name) > 100:
            continue
        known = taxonomy.lookup(name)
        aliases = (known.name, *known.synonyms) if known else (name,)
        if not any(mentions(alias, text) for alias in aliases):
            dropped.append(name)
            continue
        canonical_name = known.name if known else name
        skills.setdefault(
            match_key(canonical_name),
            SuggestedSkill(
                name=canonical_name,
                canonical=known is not None,
                category=known.category if known else None,
                evidence=item.evidence.strip()[:200],
            ),
        )
    for mention in taxonomy.find_mentions(text):
        skills.setdefault(
            match_key(mention.skill.name),
            SuggestedSkill(
                name=mention.skill.name,
                canonical=True,
                category=mention.skill.category,
                evidence=mention.snippet,
            ),
        )
    return list(skills.values()), dedupe(dropped)


_STATION_KINDS: list[tuple[str, StationKind]] = [
    (r"praktik|intern\b|internship", "internship"),
    (r"werkstudent|working student|studentische hilfskraft|hiwi", "working_student"),
    (r"auszubildend|ausbildung|azubi|apprentice|trainee", "apprenticeship"),
]


def classify_station(role: str) -> StationKind:
    lowered = role.casefold()
    for pattern, kind in _STATION_KINDS:
        if re.search(pattern, lowered):
            return kind
    return "employment"


# --- Contact ---

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)*\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s/().-]{6,}\d")
# Date ranges like "03/2019 - 05/2021" or "2019 - 2021" also look like phone numbers.
DATE_LIKE_RE = re.compile(r"\b\d{1,2}[./]\d{4}\b|\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b")


def normalize_contact(raw: LlmContact, text: str) -> Contact:
    name = (raw.name or "").strip()
    if name.isupper():
        name = name.title()  # "JONAS MUSTER" from a CV header
    return Contact(
        name=name,
        email=_checked_email(raw.email, text),
        phone=_checked_phone(raw.phone, text),
        address=(raw.address or "").strip(),
    )


def _checked_email(email: str | None, text: str) -> str:
    email = (email or "").strip()
    if EMAIL_RE.fullmatch(email) and email.casefold() in text.casefold():
        return email
    found = EMAIL_RE.search(text)
    return found.group(0) if found else ""


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _checked_phone(phone: str | None, text: str) -> str:
    phone = (phone or "").strip()
    digits = _digits(phone)
    candidates = [m.group(0).strip() for m in PHONE_RE.finditer(text)]
    if len(digits) >= 7 and any(digits == _digits(c) for c in candidates):
        return phone
    for candidate in candidates:
        if len(_digits(candidate)) >= 9 and not DATE_LIKE_RE.search(candidate):
            return candidate
    return ""


# --- Languages ---

_LEVEL_WORDS: list[tuple[str, LanguageLevel]] = [
    ("mutterspr", "native"),
    ("native", "native"),
    ("erstsprache", "native"),
    ("verhandlungssicher", "C1"),
    ("business fluent", "C1"),
    ("fließend", "C1"),
    ("fliessend", "C1"),
    ("fluent", "C1"),
    ("sehr gut", "C1"),
    ("very good", "C1"),
    ("advanced", "C1"),
    ("fortgeschritten", "B2"),
    ("gut", "B2"),
    ("good", "B2"),
    ("intermediate", "B1"),
    ("grundkenntnisse", "A2"),
    ("basic", "A2"),
    ("anfänger", "A1"),
    ("beginner", "A1"),
]


def map_language_level(level: str) -> LanguageLevel | None:
    """Map free-text levels to CEFR. An explicit code (B2, C1, ...) always wins."""
    code = re.search(r"\b([ABC][12])\b", level.upper())
    if code:
        return code.group(1)  # type: ignore[return-value]
    lowered = level.casefold()
    for word, mapped in _LEVEL_WORDS:
        if word in lowered:
            return mapped
    return None


def normalize_languages(raw: list[LlmLanguage]) -> list[Language]:
    languages: dict[str, Language] = {}
    for item in raw:
        level = map_language_level(item.level)
        name = item.language.strip()
        if level and name and name.casefold() not in languages:
            languages[name.casefold()] = Language(language=name, level=level)
    return list(languages.values())


# --- Dates & years of experience ---


def parse_month(value: str | None, *, end: bool) -> str | None:
    """Normalize "2021-3", "03/2021", "03.2021" or "2021" to "YYYY-MM"."""
    value = (value or "").strip()
    if m := re.match(r"^(\d{4})-(\d{1,2})", value):
        year, month = int(m[1]), int(m[2])
    elif m := re.fullmatch(r"(\d{1,2})[./](\d{4})", value):
        year, month = int(m[2]), int(m[1])
    elif re.fullmatch(r"\d{4}", value):
        year, month = int(value), 12 if end else 1
    else:
        return None
    if not (1900 <= year <= 2100 and 1 <= month <= 12):
        return None
    return f"{year:04d}-{month:02d}"


def _month_index(value: str) -> int:
    year, month = value.split("-")
    return int(year) * 12 + int(month) - 1


# How much a month of each kind of station counts towards professional experience.
STATION_WEIGHTS: dict[StationKind, float] = {
    "employment": 1.0,
    "working_student": 0.5,
    "apprenticeship": 0.5,
    "internship": 0.0,
}


def experience_years(stations: list[Station], today: date) -> float | None:
    """Years of professional experience from stations.

    Overlapping months count once, with the highest weight of the stations that cover them.
    """
    now = today.year * 12 + today.month - 1
    weights: dict[int, float] = {}
    for s in stations:
        if not s.start or not (s.end or s.current):
            continue
        end = min(now, _month_index(s.end)) if s.end else now
        for month in range(_month_index(s.start), end + 1):
            weights[month] = max(weights.get(month, 0.0), STATION_WEIGHTS[s.kind])
    if not weights:
        return None
    return round(sum(weights.values()) / 12, 1)
