from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from schemas import RefreshRemotesResponse
from services.admin import get_admin_service, AdminService


router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()


async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    admin_service: AdminService = Depends(get_admin_service)
) -> None:
    """
    Verify the bearer token for admin authentication.

    Args:
        credentials: HTTP authorization credentials from request header
        admin_service: Admin service instance

    Raises:
        401: Invalid or missing token
        500: Server configuration error (token not configured)
    """
    token = credentials.credentials
    try:
        if not await admin_service.verify_token(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/refresh_remotes",
    response_model=RefreshRemotesResponse,
    responses={
        401: {"description": "Invalid or missing authentication token"},
        500: {
            "description": (
                "Server configuration error (token not configured) "
                "or refresh operation failed"
            )
        }
    }
)
async def refresh_remotes(
    _: None = Depends(verify_admin_token),
    admin_service: AdminService = Depends(get_admin_service)
):
    """
    Trigger a hot reset/refresh of remote metadata.

    This endpoint requires bearer token authentication in the Authorization
    header:
    ```
    Authorization: Bearer <your-token>
    ```

    Returns:
        RefreshRemotesResponse: List of remotes that were refreshed

    Raises:
        401: Invalid or missing authentication token
        500: Refresh operation failed
    """
    try:
        remotes = await admin_service.refresh_remotes()
        return RefreshRemotesResponse(remotes=remotes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh remotes: {str(e)}"
        )
