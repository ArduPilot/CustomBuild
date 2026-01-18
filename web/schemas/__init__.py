"""
API schemas for the CustomBuild application.

This module exports all Pydantic models used for request/response validation
across the API endpoints.
"""

# Admin schemas
from .admin import (
    RefreshRemotesResponse,
)

# Build schemas
from .builds import (
    RemoteInfo,
    BuildProgress,
    BuildRequest,
    BuildSubmitResponse,
    BuildOut,
)

# Vehicle schemas
from .vehicles import (
    VehicleBase,
    VersionBase,
    VersionOut,
    BoardBase,
    BoardOut,
    CategoryBase,
    FeatureDefault,
    FeatureBase,
    FeatureOut,
)

__all__ = [
    # Admin
    "RefreshRemotesResponse",
    # Builds
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
    "CategoryBase",
    "FeatureDefault",
    "FeatureBase",
    "FeatureOut",
]
