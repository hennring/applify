from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applify.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))  # cv / certificate / sample_letter
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    # none / running / done / failed
    extraction_status: Mapped[str] = mapped_column(String(20), server_default="none")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    extraction_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extracted_at: Mapped[datetime | None]
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    seniority_years: Mapped[float | None]
    salary_min: Mapped[int | None]
    remote_pref: Mapped[str] = mapped_column(String(10), server_default="hybrid")
    exclude_keywords: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    exclude_companies: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    preferred_companies: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    tone: Mapped[str] = mapped_column(Text, server_default="")
    cover_letter_bullets: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    contact: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    skills: Mapped[list["ProfileSkill"]] = relationship(
        cascade="all, delete-orphan", order_by="ProfileSkill.position"
    )
    locations: Mapped[list["ProfileLocation"]] = relationship(
        cascade="all, delete-orphan", order_by="ProfileLocation.position"
    )
    languages: Mapped[list["ProfileLanguage"]] = relationship(
        cascade="all, delete-orphan", order_by="ProfileLanguage.position"
    )


class ProfileSkill(Base):
    __tablename__ = "profile_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    position: Mapped[int]
    skill: Mapped[str] = mapped_column(String(100))
    canonical: Mapped[bool]  # True if `skill` is a name from skills.yaml
    category: Mapped[str | None] = mapped_column(String(30))
    weight: Mapped[str] = mapped_column(String(10))  # must / nice / avoid
    level: Mapped[str | None] = mapped_column(String(10))  # basic / good / expert
    source: Mapped[str] = mapped_column(String(10))  # cv / user


class ProfileLocation(Base):
    __tablename__ = "profile_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    radius_km: Mapped[int]
    # Filled from GeoNames in M2.
    lat: Mapped[float | None]
    lon: Mapped[float | None]


class ProfileLanguage(Base):
    __tablename__ = "profile_languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    position: Mapped[int]
    language: Mapped[str] = mapped_column(String(50))
    level: Mapped[str] = mapped_column(String(10))  # A1-C2 / native


class Job(Base):
    """A posting, shared by all users; one row per real job across sources (F9)."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(300))
    location_raw: Mapped[str] = mapped_column(String(300), server_default="")
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    # Inhabitants of the town, from GeoNames; None if the place is unknown or remote.
    population: Mapped[int | None]
    # Towns named in location_raw, as GeoNames spells them; several for multi-site postings.
    cities: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    remote_type: Mapped[str | None] = mapped_column(String(10))  # hybrid / remote
    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    description: Mapped[str] = mapped_column(Text, server_default="")
    has_full_text: Mapped[bool] = mapped_column(server_default="false")
    posted_at: Mapped[datetime | None]
    # Dedup keys (§5.2).
    company_norm: Mapped[str] = mapped_column(String(300))
    title_norm: Mapped[str] = mapped_column(String(300))
    city_norm: Mapped[str] = mapped_column(String(100), server_default="")
    fingerprint: Mapped[str] = mapped_column(String(40), index=True)
    # Canonical skills mentioned in title and text; None = not scanned since the last change.
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    sources: Mapped[list["JobSource"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobSource.id"
    )

    __table_args__ = (
        Index(
            "ix_jobs_dedup_trgm",
            "company_norm",
            "title_norm",
            postgresql_using="gin",
            postgresql_ops={"company_norm": "gin_trgm_ops", "title_norm": "gin_trgm_ops"},
        ),
    )


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(30))  # ba / adzuna / ats:personio / ...
    external_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000), server_default="")
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="sources")

    __table_args__ = (UniqueConstraint("source", "external_id"),)


class Company(Base):
    """An employer, shared by all users; its careers page is read via an ATS feed (F7)."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    name_norm: Mapped[str] = mapped_column(String(300), unique=True)
    website: Mapped[str | None] = mapped_column(String(500))
    careers_url: Mapped[str | None] = mapped_column(String(1000))
    # personio / greenhouse / lever / recruitee / smartrecruiters / workday / jsonld / unknown
    ats_type: Mapped[str] = mapped_column(String(20), server_default="unknown")
    ats_token: Mapped[str | None] = mapped_column(String(200))
    discovered_from: Mapped[str] = mapped_column(String(20))  # jobs / github / wikidata / user
    detection_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    # Leads for the detection: URLs from postings, GitHub login, ...
    hints: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    detected_at: Mapped[datetime | None]
    last_checked_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UserCompany(Base):
    __tablename__ = "user_companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), server_default="candidate")  # watch / ignore
    added_at: Mapped[datetime] = mapped_column(server_default=func.now())

    company: Mapped[Company] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "company_id"),)


class SourceSetting(Base):
    """Per user and source: on/off and settings such as API keys (F7d)."""

    __tablename__ = "source_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(server_default="true")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")

    __table_args__ = (UniqueConstraint("user_id", "source"),)


class CoverageSample(Base):
    """A job the user found by hand elsewhere, checked against the stock (F10a, §5.7)."""

    __tablename__ = "coverage_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    url: Mapped[str] = mapped_column(String(1000), server_default="")
    company: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str] = mapped_column(String(200), server_default="")
    found_via: Mapped[str] = mapped_column(String(50), server_default="")
    matched_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    matched_sources: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    # discovery / adapter / missing / filter, None if found and visible
    miss_reason: Mapped[str | None] = mapped_column(String(20))
    checked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # running / done / failed / canceled
    # Set by the user; the run stops at its next progress update.
    cancel_requested: Mapped[bool] = mapped_column(server_default="false")
    # 0..1 and the step currently running, for the progress display (F5).
    progress: Mapped[float] = mapped_column(server_default="0")
    step: Mapped[str] = mapped_column(String(300), server_default="")
    # Per source: found / new / duplicates / errors (F7d).
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]


class JobMatch(Base):
    """A job rated against one user's profile (§5.3)."""

    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    score: Mapped[int]
    # Points and evidence per component, the basis of the explanation in the UI (F12).
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    # Set if a hard filter hides the job.
    excluded_reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), server_default="new")  # new / seen
    seen_at: Mapped[datetime | None]
    # The run that found the job for this user first.
    run_id: Mapped[int | None] = mapped_column(ForeignKey("search_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    scored_at: Mapped[datetime] = mapped_column(server_default=func.now())

    job: Mapped[Job] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "job_id"),)


# --- raw layer of the market analysis (§5.8, D21) ----------------------------------------
# Append-only landing tables written by search runs and read by the analytics pipeline.
# No foreign keys: raw data outlives merges and deletions in the app tables.

RAW_SCHEMA = "raw"


class JobSighting(Base):
    """One posting seen by one search run."""

    __tablename__ = "job_sightings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(index=True)
    seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    source: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(200))
    # The job the posting belonged to when seen; dedup merges may change it later.
    job_id: Mapped[int | None] = mapped_column(index=True)
    content_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_job_sightings_source_external_id", "source", "external_id"),
        {"schema": RAW_SCHEMA},
    )


class JobVersion(Base):
    """A posting's content as delivered by its source, stored once per distinct content."""

    __tablename__ = "job_versions"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(200))
    job_id: Mapped[int | None]
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    location_raw: Mapped[str] = mapped_column(Text, server_default="")
    remote_type: Mapped[str | None] = mapped_column(String(10))
    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    description: Mapped[str] = mapped_column(Text, server_default="")
    has_full_text: Mapped[bool]
    posted_at: Mapped[datetime | None]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_job_versions_source_external_id", "source", "external_id"),
        {"schema": RAW_SCHEMA},
    )
