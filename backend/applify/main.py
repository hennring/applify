import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from applify.api import documents, health, jobs, profile, runs
from applify.config import get_settings
from applify.db.session import get_sessionmaker
from applify.services.cv_jobs import fail_interrupted_jobs
from applify.services.search_runner import fail_interrupted_runs

log = logging.getLogger(__name__)


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA; unknown paths fall back to the SPA shell."""
    index = static_dir / "200.html"
    if not index.is_file():
        return
    app.mount("/_app", StaticFiles(directory=static_dir / "_app"), name="spa-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        with get_sessionmaker()() as session:
            fail_interrupted_jobs(session)
            fail_interrupted_runs(session)
    except SQLAlchemyError:
        log.warning("could not reset interrupted jobs", exc_info=True)
    yield


def create_app(*, run_startup_tasks: bool = True) -> FastAPI:
    app = FastAPI(
        title="Applify", version="0.1.0", lifespan=lifespan if run_startup_tasks else None
    )
    for module in (health, documents, profile, runs, jobs):
        app.include_router(module.router, prefix="/api")
    mount_spa(app, get_settings().static_dir)
    return app


app = create_app()
