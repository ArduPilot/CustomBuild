#!/usr/bin/env python3

"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import threading
import os
import argparse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.v1 import router as v1_router
from ui import router as ui_router

from core.config import get_settings
from core.startup import initialize_application
from core.logging_config import setup_logging
from core.limiter import limiter, rate_limit_exceeded_handler

import ap_git
import metadata_manager
import build_manager

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    settings = get_settings()

    initialize_application(settings.base_dir)

    repo = ap_git.GitRepo.clone_if_needed(
        source=settings.ap_git_url,
        dest=settings.source_dir,
        recurse_submodules=True,
    )

    vehicles_manager = metadata_manager.VehiclesManager()

    ap_src_metadata_fetcher = metadata_manager.APSourceMetadataFetcher(
        ap_repo=repo,
        caching_enabled=True,
        redis_host=settings.redis_host,
        redis_port=settings.redis_port,
    )

    versions_fetcher = metadata_manager.VersionsFetcher(
        remotes_json_path=settings.remotes_json_path,
        ap_repo=repo
    )
    versions_fetcher.reload_remotes_json()

    build_mgr = build_manager.BuildManager(
        outdir=settings.outdir_parent,
        redis_host=settings.redis_host,
        redis_port=settings.redis_port
    )

    cleaner = build_manager.BuildArtifactsCleaner()
    progress_updater = build_manager.BuildProgressUpdater()

    inbuilt_builder = None
    inbuilt_builder_thread = None
    if settings.enable_inbuilt_builder:
        from builder.builder import Builder  # noqa: E402
        inbuilt_builder = Builder(
            workdir=settings.workdir_parent,
            source_repo=repo
        )
        inbuilt_builder_thread = threading.Thread(
            target=inbuilt_builder.run,
            daemon=True
        )
        inbuilt_builder_thread.start()

    versions_fetcher.start()
    cleaner.start()
    progress_updater.start()

    app.state.repo = repo
    app.state.ap_src_metadata_fetcher = ap_src_metadata_fetcher
    app.state.versions_fetcher = versions_fetcher
    app.state.vehicles_manager = vehicles_manager
    app.state.build_manager = build_mgr
    app.state.inbuilt_builder = inbuilt_builder
    app.state.inbuilt_builder_thread = inbuilt_builder_thread
    app.state.limiter = limiter

    yield

    # Shutdown
    versions_fetcher.stop()
    cleaner.stop()
    progress_updater.stop()
    if inbuilt_builder is not None:
        inbuilt_builder.shutdown()
        if (inbuilt_builder_thread is not None and
                inbuilt_builder_thread.is_alive()):
            inbuilt_builder_thread.join()


# Create FastAPI application
app = FastAPI(
    title="CustomBuild API",
    description="API for ArduPilot Custom Firmware Builder",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# SlowAPIMiddleware is used for rate limiting
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Mount static files
WEB_ROOT = Path(__file__).resolve().parent
app.mount(
    "/static",
    StaticFiles(directory=str(WEB_ROOT / "static")),
    name="static"
)

# Include API v1 router
app.include_router(v1_router, prefix="/api")

# Include Web UI router
app.include_router(ui_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CustomBuild API Server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WEB_PORT", 8080)),
        help="Port to run the server on (default: 8080 or WEB_PORT env var)"
    )
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=args.port,
        reload=True
    )
