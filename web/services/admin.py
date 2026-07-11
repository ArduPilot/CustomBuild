"""
Admin service for handling administrative operations.
"""
import logging
from typing import List

from fastapi import Depends, Request
from web.core.config import get_settings, Settings


logger = logging.getLogger(__name__)


class AdminService:
    """Service for managing administrative operations."""

    def __init__(self, admin_token: str, versions_manager=None):
        """
        Initialize the admin service.

        Args:
            admin_token: Admin API authentication token
            versions_manager: VersionsManager instance for managing remotes
        """
        self.admin_token = admin_token
        self.versions_manager = versions_manager

    async def verify_admin_token(self, token: str) -> bool:
        """
        Verify that the provided token matches the expected admin token.

        Args:
            token: The token to verify

        Returns:
            True if token is valid, False otherwise
        """
        if not token:
            return False

        return token == self.admin_token

    async def refresh_versions(self) -> List[str]:
        """
        Refresh all version providers and sync git remotes.

        Returns:
            List of git remote names synced after the refresh

        Raises:
            Exception: If refresh operation fails
        """
        logger.info("Triggering version provider refresh")

        self.versions_manager.refresh_all()

        remotes_info = self.versions_manager.get_all_remotes_info()
        remotes_synced = [remote.name for remote in remotes_info]

        logger.info(
            f"Successfully refreshed version providers; "
            f"synced {len(remotes_synced)} remotes: {remotes_synced}"
        )

        return remotes_synced


def get_admin_service(
    request: Request,
    settings: Settings = Depends(get_settings)
) -> AdminService:
    """
    Get AdminService instance with dependencies from app state.

    Args:
        request: FastAPI Request object
        settings: Application settings

    Returns:
        AdminService instance initialized with app state dependencies

    Raises:
        RuntimeError: If admin token is not configured
    """
    admin_token = settings.admin_token

    if admin_token is None:
        raise RuntimeError("Admin token not configured on server")

    return AdminService(
        admin_token=admin_token,
        versions_manager=request.app.state.versions_manager
    )
