from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from applify.api import health
from applify.config import get_settings


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


def create_app() -> FastAPI:
    app = FastAPI(title="Applify", version="0.1.0")
    app.include_router(health.router, prefix="/api")
    mount_spa(app, get_settings().static_dir)
    return app


app = create_app()
