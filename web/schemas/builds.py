from typing import List, Literal

from pydantic import BaseModel, Field
from schemas.vehicles import VehicleBase, BoardBase, RemoteInfo


# --- Build Progress ---
class BuildProgress(BaseModel):
    """Build progress and status information."""
    percent: int = Field(
        ..., ge=0, le=100, description="Build completion percentage"
    )
    state: Literal[
        "PENDING", "RUNNING", "SUCCESS", "FAILURE", "ERROR", "TIMED_OUT"
    ] = Field(..., description="Current build state")


# --- Build Request ---
class BuildRequest(BaseModel):
    """Schema for creating a new build request."""
    vehicle_id: str = Field(
        ..., description="Vehicle ID to build for"
    )
    board_id: str = Field(
        ..., description="Board ID to build for"
    )
    version_id: str = Field(
        ..., description="Version ID for build source code"
    )
    selected_features: List[str] = Field(
        default_factory=list,
        description="Feature IDs to enable for this build"
    )


# --- Build Submit Response ---
class BuildSubmitResponse(BaseModel):
    """Response schema for build submission."""
    build_id: str = Field(..., description="Unique build identifier")
    url: str = Field(..., description="URL to get build details")
    status: Literal["submitted"] = Field(
        ..., description="Build submission status"
    )


# --- Build Version Info ---
class BuildVersionInfo(BaseModel):
    """Version information for a build."""
    id: str = Field(..., description="Version ID used for this build")
    remote_info: RemoteInfo = Field(
        ..., description="Source repository information"
    )
    git_hash: str = Field(..., description="Git commit hash used for build")


# --- Build Output ---
class BuildOut(BaseModel):
    """Complete build information output schema."""
    build_id: str = Field(..., description="Unique build identifier")
    vehicle: VehicleBase = Field(..., description="Target vehicle information")
    board: BoardBase = Field(..., description="Target board information")
    version: BuildVersionInfo = Field(
        ..., description="Version information for this build"
    )
    selected_features: List[str] = Field(
        default_factory=list,
        description="Enabled feature flags for this build"
    )
    progress: BuildProgress = Field(
        ..., description="Current build status and progress"
    )
    time_created: float = Field(
        ..., description="Unix timestamp when build was created"
    )
