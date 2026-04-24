"""FastAPI app factory: CORS, router mounting, health check, startup init."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import (
    auth_routes,
    chat_routes,
    dashboard_routes,
    export_routes,
    scrape_routes,
)
from backend.app.config import settings
from backend.app.database import Base, engine, SessionLocal
from backend.app.init_db import seed_buildings, seed_users


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fitzrovia Rental Comp API",
        version="1.0.0",
        description="Internal API powering the asset management competitive rental dashboard.",
    )

    # CORS. allowed_origin is a comma-separated string; split + strip so a single
    # env var can carry both local dev and production frontend URLs.
    origins = [o.strip() for o in settings.allowed_origin.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_routes.router)
    app.include_router(dashboard_routes.router)
    app.include_router(scrape_routes.router)
    app.include_router(export_routes.router)
    app.include_router(chat_routes.router)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok", "env": settings.env}

    @app.on_event("startup")
    def startup():
        """On startup: ensure schema + baseline seed data exist.

        On Render free tier the DB is ephemeral between deploys (SQLite on local disk),
        so we create tables and seed the 11 buildings + 2 users on every boot. The
        seed functions are idempotent — existing rows are skipped."""
        log.info("Initializing schema and seed data...")
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            nb = seed_buildings(db)
            nu = seed_users(db)
            log.info(f"Seeded {nb} new buildings, {nu} new users")
        finally:
            db.close()

    return app


app = create_app()
