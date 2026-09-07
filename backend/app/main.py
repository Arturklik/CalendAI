import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect

from app import models  # noqa: F401 — register ORM metadata
from app.api import ai, auth, events, sync
from app.config import get_settings
from app.database import Base, engine


def _ensure_schema() -> None:
    settings = get_settings()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    events_columns = {col["name"] for col in inspector.get_columns("events")} if "events" in tables else set()
    stale = "calendars" in tables or ("events" in tables and "user_id" not in events_columns)
    if stale and settings.database_url.startswith("sqlite"):
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_schema()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="CalendAI backend — auth, events CRUD, differential sync, AI parse",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(sync.router, prefix="/api/v1")
    app.include_router(ai.router, prefix="/api/v1")

    web_dir = _ROOT / "web"
    if web_dir.exists():
        app.mount("/web", StaticFiles(directory=web_dir), name="web")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(web_dir / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
