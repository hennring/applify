from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, ForeignKey, Integer, String, Text, func
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
