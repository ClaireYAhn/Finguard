"""FinGuard API: gateway (/v1), agent guard (/v1/guard) and control-panel API (/api)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import actions  # noqa: F401  (registers checks)
from gateway.routes import router as gateway_router
from policies import store as policies

from .config import get_settings
from .db import get_db
from .routes_admin import public as admin_public
from .routes_admin import router as admin_router
from .routes_guard import router as guard_router

log = logging.getLogger("finguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    n = policies.seed_packs()
    s = get_settings()
    if s.admin_password == "change-me-admin":
        log.warning("FINGUARD_ADMIN_PASSWORD is the default. Set it in .env before sharing this instance.")
    log.info("FinGuard started: provider=%s engine=%s packs_seeded=%s", s.provider, s.engine, n)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="FinGuard", version="0.1.0", lifespan=lifespan,
                  description="AI governance gateway and control panel for financial services (demo data is fictional).")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-FinGuard-Action", "X-FinGuard-Request-Id", "X-FinGuard-Rules", "X-FinGuard-Engine", "X-FinGuard-Policy-Version"])
    app.include_router(gateway_router)
    app.include_router(guard_router)
    app.include_router(admin_public)
    app.include_router(admin_router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:  # never leak stack traces
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"error": "Something went wrong inside FinGuard. The request was not processed."}, status_code=500)

    return app


app = create_app()
