# app/schemas/vehicles.py
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- Vehicles ---
class VehicleBase(BaseModel):
    id: str = Field(..., description="Unique vehicle identifier")
    name: str = Field(..., description="Vehicle display name")


# --- Remote Information ---
class RemoteInfo(BaseModel):
    """Git remote repository information."""
    name: str = Field(..., description="Remote name (e.g., 'ardupilot')")
    url: str = Field(..., description="Git repository URL")


# --- Versions ---
class VersionBase(BaseModel):
    id: str = Field(..., description="Unique version identifier")
    name: str = Field(..., description="Version display name")
    type: Literal["beta", "stable", "latest", "tag"] = Field(
        ..., description="Version type classification"
    )
    remote: RemoteInfo = Field(
        ..., description="Git remote repository information for the version"
    )
    commit_ref: Optional[str] = Field(
        None, description="Git reference (tag, branch name, or commit SHA)"
    )


class VersionOut(VersionBase):
    vehicle_id: str = Field(
        ..., description="Vehicle identifier associated with this version"
    )


# --- Boards ---
class BoardBase(BaseModel):
    id: str = Field(..., description="Unique board identifier")
    name: str = Field(..., description="Board display name")


class BoardOut(BoardBase):
    vehicle_id: str = Field(..., description="Associated vehicle identifier")
    version_id: str = Field(..., description="Associated version identifier")


# --- Features ---
class CategoryBase(BaseModel):
    id: str = Field(..., description="Unique category identifier")
    name: str = Field(..., description="Category display name")
    description: Optional[str] = Field(
        None, description="Category description"
    )


class FeatureDefault(BaseModel):
    enabled: bool = Field(
        ..., description="Whether feature is enabled by default"
    )
    source: Literal["firmware-server", "build-options-py"] = Field(
        ...,
        description=(
            "Source of the default value: 'firmware-server' from "
            "firmware.ardupilot.org, 'build-options-py' from git repository"
        )
    )


class FeatureBase(BaseModel):
    id: str = Field(..., description="Unique feature identifier/flag name")
    name: str = Field(..., description="Feature display name")
    category: CategoryBase = Field(..., description="Feature category")
    description: Optional[str] = Field(
        None, description="Feature description"
    )


class FeatureOut(FeatureBase):
    vehicle_id: str = Field(..., description="Associated vehicle identifier")
    version_id: str = Field(..., description="Associated version identifier")
    board_id: str = Field(..., description="Associated board identifier")
    default: FeatureDefault = Field(
        ..., description="Default state for this feature on this board"
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of feature IDs that this feature depends on"
    )
