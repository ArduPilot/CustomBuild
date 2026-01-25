from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path

from schemas import (
    VehicleBase,
    VersionOut,
    BoardOut,
    FeatureOut,
)
from services.vehicles import get_vehicles_service, VehiclesService

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=List[VehicleBase])
async def list_vehicles(
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get list of all available vehicles.

    Returns:
        List of vehicles with their IDs and names.
    """
    return service.get_all_vehicles()


@router.get(
    "/{vehicle_id}",
    response_model=VehicleBase,
    responses={
        404: {"description": "Vehicle not found"}
    }
)
async def get_vehicle(
    vehicle_id: str = Path(..., description="Unique vehicle identifier"),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get a specific vehicle by ID.

    Args:
        vehicle_id: The vehicle identifier (e.g., 'copter', 'plane')

    Returns:
        Vehicle details
    """
    vehicle = service.get_vehicle(vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle with id '{vehicle_id}' not found"
        )
    return vehicle


# --- Version Endpoints ---
@router.get("/{vehicle_id}/versions", response_model=List[VersionOut])
async def list_versions(
    vehicle_id: str = Path(..., description="Vehicle identifier"),
    type: Optional[str] = Query(
        None,
        description=(
            "Filter by version type "
            "(beta, stable, latest, tag)"
        )
    ),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get all versions available for a specific vehicle.

    Args:
        vehicle_id: The vehicle identifier
        type: Optional filter by version type

    Returns:
        List of versions for the vehicle
    """
    return service.get_versions(vehicle_id, type_filter=type)


@router.get(
    "/{vehicle_id}/versions/{version_id}",
    response_model=VersionOut,
    responses={
        404: {"description": "Version not found for the vehicle"}
    }
)
async def get_version(
    vehicle_id: str = Path(..., description="Vehicle identifier"),
    version_id: str = Path(..., description="Version identifier"),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get details of a specific version for a vehicle.

    Args:
        vehicle_id: The vehicle identifier
        version_id: The version identifier

    Returns:
        Version details
    """
    version = service.get_version(vehicle_id, version_id)
    if not version:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Version '{version_id}' not found for "
                f"vehicle '{vehicle_id}'"
            )
        )
    return version


# --- Board Endpoints ---
@router.get(
    "/{vehicle_id}/versions/{version_id}/boards",
    response_model=List[BoardOut],
    responses={
        404: {"description": "No boards found for the vehicle version"}
    }
)
async def list_boards(
    vehicle_id: str = Path(..., description="Vehicle identifier"),
    version_id: str = Path(..., description="Version identifier"),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get all boards available for a specific vehicle version.

    Args:
        vehicle_id: The vehicle identifier
        version_id: The version identifier

    Returns:
        List of boards for the vehicle version
    """
    boards = service.get_boards(vehicle_id, version_id)
    if not boards:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No boards found for vehicle '{vehicle_id}' and "
                f"version '{version_id}'"
            )
        )

    return boards


@router.get(
    "/{vehicle_id}/versions/{version_id}/boards/{board_id}",
    response_model=BoardOut,
    responses={
        404: {"description": "Board not found"}
    }
)
async def get_board(
    vehicle_id: str = Path(..., description="Vehicle identifier"),
    version_id: str = Path(..., description="Version identifier"),
    board_id: str = Path(..., description="Board identifier"),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get details of a specific board for a vehicle version.

    Args:
        vehicle_id: The vehicle identifier
        version_id: The version identifier
        board_id: The board identifier

    Returns:
        Board details
    """
    board = service.get_board(vehicle_id, version_id, board_id)
    if not board:
        raise HTTPException(
            status_code=404,
            detail=f"Board '{board_id}' not found"
        )
    return board


# --- Feature Endpoints ---
@router.get(
    "/{vehicle_id}/versions/{version_id}/boards/{board_id}/features",
    response_model=List[FeatureOut]
)
async def list_features(
    vehicle_id: str = Path(..., description="Vehicle identifier"),
    version_id: str = Path(..., description="Version identifier"),
    board_id: str = Path(..., description="Board identifier"),
    category_id: Optional[str] = Query(
        None, description="Filter by category ID"
    ),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get all features with defaults for a specific vehicle/version/board.

    Args:
        vehicle_id: The vehicle identifier
        version_id: The version identifier
        board_id: The board identifier
        category_id: Optional filter by category

    Returns:
        List of features with default settings for the board
    """
    features = service.get_features(
        vehicle_id, version_id, board_id, category_id
    )
    return features


@router.get(
    "/{vehicle_id}/versions/{version_id}/boards/{board_id}/"
    "features/{feature_id}",
    response_model=FeatureOut,
    responses={
        404: {"description": "Feature not found"}
    }
)
async def get_feature(
    vehicle_id: str = Path(..., description="Vehicle identifier"),
    version_id: str = Path(..., description="Version identifier"),
    board_id: str = Path(..., description="Board identifier"),
    feature_id: str = Path(..., description="Feature identifier"),
    service: VehiclesService = Depends(get_vehicles_service)
):
    """
    Get details of a specific feature for a vehicle/version/board.

    Args:
        vehicle_id: The vehicle identifier
        version_id: The version identifier
        board_id: The board identifier
        feature_id: The feature identifier

    Returns:
        Feature details with default settings
    """
    feature = service.get_feature(
        vehicle_id, version_id, board_id, feature_id
    )
    if not feature:
        raise HTTPException(
            status_code=404,
            detail=f"Feature '{feature_id}' not found"
        )
    return feature
