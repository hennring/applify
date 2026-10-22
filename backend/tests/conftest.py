import copy
import os
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from applify.config import Settings, get_settings
from applify.db.session import get_session, get_session_factory
from applify.llm import get_llm
from applify.llm.base import T
from applify.main import create_app
from applify.services.background import get_search_runner, get_task_runner
from applify.sources import get_client_factory, get_sources_factory
from applify.sources.base import JobPosting, RunSources, SearchQuery
from applify.sources.http import PoliteClient

BACKEND_DIR = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
TEST_DATABASE_URL = os.environ.get(
    "APPLIFY_TEST_DATABASE_URL",
    "postgresql+psycopg://applify:applify@127.0.0.1:5432/applify_test",
)


class FakeLLM:
    """LLMProvider that returns prepared structured results."""

    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.calls: list[str] = []

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append(prompt)
        return str(self.result)

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        self.calls.append(prompt)
        if isinstance(self.result, Exception):
            raise self.result
        return schema.model_validate(self.result)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """A fresh test database, migrated with Alembic. Skips if Postgres is not running."""
    url = make_url(TEST_DATABASE_URL)
    admin_dsn = (
        f"host={url.host} port={url.port} user={url.username} "
        f"password={url.password} dbname=postgres connect_timeout=3"
    )
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
            conn.execute(f'CREATE DATABASE "{url.database}"')
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not available: {exc}")

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")

    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Session inside a transaction that is rolled back after each test."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()


class FakeSource:
    """JobSource with prepared postings per search term.

    complete() adds a generic full text, or the text from `texts` if that is set
    (postings without an entry there stay short info).
    """

    name = "ba"
    label = "Bundesagentur für Arbeit"
    located = True

    def __init__(self) -> None:
        self.postings: dict[str, list[JobPosting]] = {}
        self.errors: dict[str, Exception] = {}
        self.queries: list[SearchQuery] = []
        self.completed: list[str] = []
        self.texts: dict[str, str] | None = None

    def search(self, query: SearchQuery) -> list[JobPosting]:
        self.queries.append(query)
        if query.term in self.errors:
            raise self.errors[query.term]
        return [copy.deepcopy(p) for p in self.postings.get(query.term, [])]

    def complete(self, posting: JobPosting) -> JobPosting:
        self.completed.append(posting.external_id)
        if self.texts is None:
            posting.description = f"Volltext zu {posting.title}. " * 20
        else:
            posting.description = self.texts.get(posting.external_id, "")
        posting.has_full_text = len(posting.description) >= 200
        return posting


class FakeWeb:
    """Mock transport serving prepared responses by URL (query ignored); others get 404."""

    def __init__(self) -> None:
        self.pages: dict[str, httpx.Response | Callable[[httpx.Request], httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def add(self, url: str, body: str | bytes | dict[str, Any] | list[Any], **kwargs: Any) -> None:
        if isinstance(body, dict | list):
            self.pages[url] = httpx.Response(200, json=body, **kwargs)
        else:
            self.pages[url] = httpx.Response(200, content=body, **kwargs)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url).split("?")[0]
        page = self.pages.get(url)
        if page is None:
            return httpx.Response(404)
        return page(request) if callable(page) else page

    def urls(self) -> list[str]:
        return [str(r.url).split("?")[0] for r in self.requests]

    def client(self, contact: str = "me@example.org") -> PoliteClient:
        return PoliteClient(interval=0, transport=httpx.MockTransport(self), contact=contact)


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
def fake_source() -> FakeSource:
    return FakeSource()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def run_sources(fake_source: FakeSource) -> RunSources:
    """What a search run in the API tests reaches; tests may add feeds or a web client."""
    return RunSources([fake_source])


@pytest.fixture
def api(
    db_session: Session,
    fake_llm: FakeLLM,
    run_sources: RunSources,
    web: FakeWeb,
    tmp_path: Path,
) -> Iterator[TestClient]:
    """API client on the test database; background jobs run synchronously."""
    app = create_app(run_startup_tasks=False)
    settings = Settings(data_dir=tmp_path, static_dir=tmp_path / "no-spa")
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_session_factory] = lambda: lambda: nullcontext(db_session)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_task_runner] = lambda: lambda fn, *args: fn(*args)
    app.dependency_overrides[get_search_runner] = lambda: lambda fn, *args: fn(*args)
    app.dependency_overrides[get_sources_factory] = lambda: lambda settings: run_sources
    app.dependency_overrides[get_client_factory] = lambda: lambda settings: web.client()
    with TestClient(app) as client:
        yield client
