"""Deployment entry point: the existing API and Vite assets on one origin."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.main import app as api_app
from backend.app.seed import ROOT


def create_app(static_dir: Path | None = None) -> FastAPI:
    directory = static_dir or Path(os.getenv("FRONTEND_DIST", ROOT / "frontend/dist"))
    if not (directory / "index.html").is_file() or not (directory / "assets").is_dir():
        raise RuntimeError("Build the frontend before starting the deployment app")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(directory / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/assets", StaticFiles(directory=directory / "assets"), name="assets")
    # Keep the original API paths, handlers, middleware and OpenAPI intact.
    app.mount("/", api_app)
    return app
