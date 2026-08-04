"""
API schemas for the CustomBuild application.

This module exports all Pydantic models used for request/response validation
across the API endpoints.
"""

# Admin schemas
from backend.schemas.admin import (
    RefreshVersionsResponse,
)

# Build schemas
from backend.schemas.builds import (
    BuildVersionInfo,
    RemoteInfo,
    BuildProgress,
    BuildRequest,
    BuildSubmitResponse,
    BuildOut,
)

# Vehicle schemas
from backend.schemas.vehicles import (
    VehicleBase,
    VersionBase,
    VersionOut,
    BoardBase,
    BoardOut,
    StandardArtifactOut,
    CategoryBase,
    FeatureDefault,
    FeatureBase,
    FeatureOut,
)

__all__ = [
    # Admin
    "RefreshVersionsResponse",
    # Builds
    "BuildVersionInfo",
    "RemoteInfo",
    "BuildProgress",
    "BuildRequest",
    "BuildSubmitResponse",
    "BuildOut",
    # Vehicles
    "VehicleBase",
    "VersionBase",
    "VersionOut",
    "BoardBase",
    "BoardOut",
    "StandardArtifactOut",
    "CategoryBase",
    "FeatureDefault",
    "FeatureBase",
    "FeatureOut",
]
