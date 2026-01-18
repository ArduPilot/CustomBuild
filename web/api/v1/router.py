"""
Main API v1 router.

This module aggregates all v1 API endpoints and provides a single router
to be included in the main FastAPI application.
"""
from fastapi import APIRouter

from . import vehicles, builds, admin

# Create the main v1 router
router = APIRouter(prefix="/v1")

# Include all sub-routers
router.include_router(vehicles.router)
router.include_router(builds.router)
router.include_router(admin.router)
