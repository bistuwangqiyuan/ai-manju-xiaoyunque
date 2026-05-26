from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routes import auth as auth_routes
from .routes import batch as batch_routes
from .routes import billing as billing_routes
from .routes import genres as genres_routes
from .routes import internal as internal_routes
from .routes import jobs as jobs_routes
from .routes import library as library_routes
from .routes import styles as styles_routes  # V10 §1.1
from .settings import settings
from .worker import worker_loop

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("xyq.api")


def _try_import(name: str):
    """Import .routes.<name>, return module or None.

    Each router is optional so the API stays bootable even while later
    phases are still landing.
    """
    try:
        from importlib import import_module
        return import_module(f".routes.{name}", package=__package__)
    except Exception as exc:  # pragma: no cover
        logger.info("router %s not yet available: %s", name, exc)
        return None


novels_routes = _try_import("novels")
screenplays_routes = _try_import("screenplays")
derivative_routes = _try_import("derivative")
orgs_routes = _try_import("orgs")
templates_routes = _try_import("templates")
schedules_routes = _try_import("schedules")
flow_routes = _try_import("flow")
public_v1_routes = _try_import("public_v1")


def _embedded_worker_enabled() -> bool:
    """
    Whether to spawn the in-process polling worker on app startup.

    Self-hosted / VM / docker-compose mode → keep TRUE (default).
    Serverless mode (CloudBase 云托管 / FC / SCF Web 函数) → set
    EMBEDDED_WORKER=0 and use external SCF cron hitting /api/internal/worker/tick.
    """
    val = os.environ.get("EMBEDDED_WORKER", "1").strip().lower()
    return val not in {"0", "false", "no", "off"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("DB initialized")
    worker_task = None
    if _embedded_worker_enabled():
        worker_task = asyncio.create_task(worker_loop())
        logger.info("Embedded worker started (mock=%s)", settings.use_mock_worker)
    else:
        logger.info("Embedded worker DISABLED (serverless mode) — use /api/internal/worker/tick")
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="小云雀 · AI 漫剧产线 API",
    version="0.1.0",
    description="Backend for the Xiaoyunque AI manga-drama production SaaS.",
    lifespan=lifespan,
    redirect_slashes=False,  # avoid 307 that can drop Authorization headers
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(jobs_routes.router, prefix="/api")
app.include_router(billing_routes.router, prefix="/api")
app.include_router(genres_routes.router, prefix="/api")
app.include_router(library_routes.router, prefix="/api")
app.include_router(batch_routes.router, prefix="/api")
app.include_router(internal_routes.router, prefix="/api")
app.include_router(styles_routes.router, prefix="/api")
for _m in (novels_routes, screenplays_routes, derivative_routes,
           orgs_routes, templates_routes, schedules_routes, flow_routes):
    if _m is not None and getattr(_m, "router", None) is not None:
        app.include_router(_m.router, prefix="/api")
if public_v1_routes is not None and getattr(public_v1_routes, "router", None) is not None:
    app.include_router(public_v1_routes.router)  # carries its own /api/v1 prefix

# Serve generated videos & covers
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "mock_worker": settings.use_mock_worker,
            "mock_billing": settings.use_mock_billing,
        }
    )


@app.get("/api/healthz")
def healthz() -> JSONResponse:
    """K8s / Helm readiness alias for ``/api/health``."""
    return health()


@app.get("/")
def root():
    return {
        "service": "xiaoyunque-api",
        "docs": "/docs",
        "health": "/api/health",
    }
