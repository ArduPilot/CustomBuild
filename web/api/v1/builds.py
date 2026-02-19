from typing import List, Optional
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Path,
    status,
    Depends,
    Request
)
from fastapi.responses import FileResponse, PlainTextResponse

from schemas import (
    BuildRequest,
    BuildSubmitResponse,
    BuildOut,
)
from services.builds import get_builds_service, BuildsService
from core.limiter import limiter

router = APIRouter(prefix="/builds", tags=["builds"])


@router.post(
    "",
    response_model=BuildSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid build configuration"},
        404: {"description": "Vehicle, board, or version not found"},
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too many requests. Try again after some time."
                    }
                }
            }
        }
    }
)
@limiter.limit("10/hour")
async def create_build(
    build_request: BuildRequest,
    request: Request,
    service: BuildsService = Depends(get_builds_service)
):
    """
    Create a new build request.

    Args:
        build_request: Build configuration including vehicle, board, version,
                      and selected features

    Returns:
        Simple response with build_id, URL, and status

    Raises:
        400: Invalid build configuration
        404: Vehicle, board, or version not found
        429: Rate limit exceeded
    """
    try:
        return service.create_build(build_request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[BuildOut])
async def list_builds(
    vehicle_id: Optional[str] = Query(
        None, description="Filter by vehicle ID"
    ),
    board_id: Optional[str] = Query(
        None, description="Filter by board ID"
    ),
    state: Optional[str] = Query(
        None,
        description="Filter by build state (PENDING, RUNNING, SUCCESS, "
                    "FAILURE, CANCELLED)"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of builds to return"
    ),
    offset: int = Query(
        0, ge=0, description="Number of builds to skip"
    ),
    service: BuildsService = Depends(get_builds_service)
):
    """
    Get list of builds with optional filters.

    Args:
        vehicle_id: Filter builds by vehicle
        board_id: Filter builds by board
        state: Filter builds by current state
        limit: Maximum number of results
        offset: Number of results to skip (for pagination)

    Returns:
        List of builds matching the filters
    """
    return service.list_builds(
        vehicle_id=vehicle_id,
        board_id=board_id,
        state=state,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{build_id}",
    response_model=BuildOut,
    responses={
        404: {"description": "Build not found"}
    }
)
async def get_build(
    build_id: str = Path(..., description="Unique build identifier"),
    service: BuildsService = Depends(get_builds_service)
):
    """
    Get details of a specific build.

    Args:
        build_id: The unique build identifier

    Returns:
        Complete build details including progress and status

    Raises:
        404: Build not found
    """
    build = service.get_build(build_id)
    if not build:
        raise HTTPException(
            status_code=404,
            detail=f"Build with id '{build_id}' not found"
        )
    return build


@router.get(
    "/{build_id}/logs",
    responses={
        404: {"description": "Build not found or logs not available yet"}
    }
)
async def get_build_logs(
    build_id: str = Path(..., description="Unique build identifier"),
    tail: Optional[int] = Query(
        None, ge=1, description="Return only the last N lines"
    ),
    service: BuildsService = Depends(get_builds_service)
):
    """
    Get build logs for a specific build.

    Args:
        build_id: The unique build identifier
        tail: Optional number of last lines to return

    Returns:
        Build logs as text

    Raises:
        404: Build not found
        404: Logs not available yet
    """
    logs = service.get_build_logs(build_id, tail)
    if logs is None:
        raise HTTPException(
            status_code=404,
            detail=f"Logs not available for build '{build_id}'"
        )
    return PlainTextResponse(content=logs)


@router.get(
    "/{build_id}/artifact",
    responses={
        404: {
            "description": (
                "Build not found or artifact not available "
            )
        }
    }
)
async def download_artifact(
    build_id: str = Path(..., description="Unique build identifier"),
    service: BuildsService = Depends(get_builds_service)
):
    """
    Download the build artifact (firmware binary).

    Args:
        build_id: The unique build identifier

    Returns:
        Binary file download

    Raises:
        404: Build not found
        404: Artifact not available (build not completed)
    """
    artifact_path = service.get_artifact_path(build_id)
    if not artifact_path:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Artifact not available for build '{build_id}'. "
                "Build may not be completed."
            )
        )
    return FileResponse(
        path=artifact_path,
        media_type='application/gzip',
        filename=f"{build_id}.tar.gz"
    )
