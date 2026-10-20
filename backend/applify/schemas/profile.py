from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Weight = Literal["must", "nice", "avoid"]
SkillLevel = Literal["basic", "good", "expert"]
LanguageLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2", "native"]
RemotePref = Literal["no", "hybrid", "remote"]
Source = Literal["cv", "user"]


class Schema(BaseModel):
    # Fields with defaults are always present in responses; marking them required in the
    # OpenAPI output schema gives the frontend non-optional types.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


# "YYYY-MM"; month-precision is enough for CV stations.
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Contact(Schema):
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""


class Skill(Schema):
    name: str = Field(min_length=1, max_length=100)
    canonical: bool = False
    category: str | None = None
    weight: Weight = "nice"
    level: SkillLevel | None = None
    source: Source = "user"


class Location(Schema):
    name: str = Field(min_length=1, max_length=200)
    radius_km: int = Field(default=30, ge=0, le=500)


class Language(Schema):
    language: str = Field(min_length=1, max_length=50)
    level: LanguageLevel


StationKind = Literal["employment", "working_student", "apprenticeship", "internship"]


class Station(Schema):
    employer: str
    role: str = ""
    kind: StationKind = "employment"
    start: str | None = Field(default=None, pattern=MONTH_PATTERN)
    end: str | None = Field(default=None, pattern=MONTH_PATTERN)
    current: bool = False


class Education(Schema):
    institution: str
    degree: str = ""
    start: str | None = Field(default=None, pattern=MONTH_PATTERN)
    end: str | None = Field(default=None, pattern=MONTH_PATTERN)


class ProfileData(Schema):
    roles: list[str] = []
    seniority_years: float | None = Field(default=None, ge=0, le=60)
    salary_min: int | None = Field(default=None, ge=0)
    remote_pref: RemotePref = "hybrid"
    skills: list[Skill] = []
    locations: list[Location] = []
    languages: list[Language] = []
    exclude_keywords: list[str] = []
    exclude_companies: list[str] = []
    preferred_companies: list[str] = []
    tone: str = ""
    cover_letter_bullets: list[str] = []
    contact: Contact = Contact()
    experience: list[Station] = []
    education: list[Education] = []


class SuggestedSkill(Schema):
    name: str
    canonical: bool
    category: str | None
    evidence: str


class CvSuggestion(Schema):
    """Validated and normalized result of a CV extraction (§5.4), stored per document."""

    contact: Contact
    roles: list[str]
    skills: list[SuggestedSkill]
    languages: list[Language]
    experience: list[Station]
    education: list[Education]
    seniority_years: float | None
    # Skills the LLM named without evidence in the CV text (shown, not applied).
    dropped_skills: list[str] = []


ChangeField = Literal[
    "contact", "roles", "skills", "languages", "experience", "education", "seniority_years"
]


class ChangeItem(Schema):
    id: str
    field: ChangeField
    kind: Literal["add", "change"]
    # Sub-field for contact changes (name/email/phone/address).
    key: str | None = None
    current: str | None = None
    suggested: str
