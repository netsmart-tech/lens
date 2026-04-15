"""FastAPI app factory + lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lens.config import settings
from lens.db.engine import get_engine, shutdown_engines
from lens.logging import configure_logging, get_logger
from lens.routers import activity, auth, health, tenants, tickets

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm the default engine so connection errors surface at boot.
    get_engine()
    log.info("lens_startup", environment=settings.environment)
    yield
    log.info("lens_shutdown")
    await shutdown_engines()


app = FastAPI(
    title="Lens — Netsmart Consulting API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_api(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(tickets.router)
app.include_router(activity.router)
