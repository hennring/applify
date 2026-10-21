from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from typing import Any, ClassVar

from sqlalchemy import DateTime, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from applify.config import get_settings


class Base(DeclarativeBase):
    # timestamptz everywhere: the API then sends times with offset, and DB defaults (UTC)
    # and times set in Python compare correctly.
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    """For background jobs, which need their own session outside the request."""
    return get_sessionmaker()


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
