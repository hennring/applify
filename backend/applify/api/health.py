from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from applify.config import Settings, get_settings
from applify.db.session import get_session

router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "error"]


class ComponentHealth(BaseModel):
    status: CheckStatus
    detail: str | None = None


class Health(BaseModel):
    status: CheckStatus
    database: ComponentHealth
    ollama: ComponentHealth


def check_database(session: Session) -> ComponentHealth:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        return ComponentHealth(status="error", detail=type(exc).__name__)
    return ComponentHealth(status="ok")


def check_ollama(settings: Settings) -> ComponentHealth:
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return ComponentHealth(status="error", detail=f"nicht erreichbar: {type(exc).__name__}")
    models = {m["name"] for m in response.json().get("models", [])}
    if settings.ollama_model not in models:
        return ComponentHealth(
            status="error", detail=f"Modell {settings.ollama_model} nicht installiert"
        )
    return ComponentHealth(status="ok", detail=settings.ollama_model)


@router.get("/health")
def health(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Health:
    database = check_database(session)
    ollama = check_ollama(settings)
    overall: CheckStatus = "ok" if database.status == ollama.status == "ok" else "error"
    return Health(status=overall, database=database, ollama=ollama)
