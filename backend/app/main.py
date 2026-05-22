from __future__ import annotations

import asyncio
import logging
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
from .routes import jobs as jobs_routes
from .routes import library as library_routes
from .settings import settings
from .worker import worker_loop

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("xyq.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("DB initialized")
    worker_task = asyncio.create_task(worker_loop())
    logger.info("Worker started (mock=%s)", settings.use_mock_worker)
    try:
        yield
    finally:
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


@app.get("/")
def root():
    return {
        "service": "xiaoyunque-api",
        "docs": "/docs",
        "health": "/api/health",
    }
