from collections.abc import Iterator
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from applify.config import Settings, get_settings
from applify.db.session import get_session
from applify.main import create_app


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(session: MagicMock) -> Iterator[TestClient]:
    app = create_app()

    def override_session() -> Iterator[MagicMock]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: Settings(ollama_model="qwen3:14b")
    with TestClient(app) as c:
        yield c


def fake_ollama(monkeypatch: pytest.MonkeyPatch, models: list[str] | Exception) -> None:
    def get(url: str, timeout: float) -> httpx.Response:
        if isinstance(models, Exception):
            raise models
        return httpx.Response(
            200,
            json={"models": [{"name": m} for m in models]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", get)


def test_all_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ollama(monkeypatch, ["qwen3:14b"])
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["ollama"] == {"status": "ok", "detail": "qwen3:14b"}


def test_model_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ollama(monkeypatch, ["qwen3:8b"])
    body = client.get("/api/health").json()
    assert body["status"] == "error"
    assert "nicht installiert" in body["ollama"]["detail"]


def test_ollama_unreachable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ollama(monkeypatch, httpx.ConnectError("refused"))
    body = client.get("/api/health").json()
    assert body["ollama"]["status"] == "error"


def test_database_error(
    client: TestClient, session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_ollama(monkeypatch, ["qwen3:14b"])
    session.execute.side_effect = RuntimeError("down")
    body = client.get("/api/health").json()
    assert body["status"] == "error"
    assert body["database"] == {"status": "error", "detail": "RuntimeError"}
