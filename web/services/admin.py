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

    def __init__(self, remote_reload_token: str, versions_fetcher=None):
        """
        Initialize the admin service.

        Args:
            remote_reload_token: Remote reload authentication token
            versions_fetcher: VersionsFetcher instance for managing remotes
        """
        self.remote_reload_token = remote_reload_token
        self.versions_fetcher = versions_fetcher

    async def verify_remote_reload_token(self, token: str) -> bool:
        """
        Verify that the provided token matches the expected remote reload token.

        Args:
            token: The token to verify

        Returns:
            True if token is valid, False otherwise
        """
        if not token:
            return False

        return token == self.remote_reload_token

    async def refresh_remotes(self) -> List[str]:
        """
        Trigger a refresh of remote metadata.

        Returns:
            List of remote names that were refreshed

        Raises:
            Exception: If refresh operation fails
        """
        logger.info("Triggering remote metadata refresh")

        # Reload remotes.json
        self.versions_fetcher.reload_remotes_json()

        # Get list of remotes that are now available
        remotes_info = self.versions_fetcher.get_all_remotes_info()
        remotes_refreshed = [remote.name for remote in remotes_info]

        logger.info(
            f"Successfully refreshed {len(remotes_refreshed)} remotes: "
            f"{remotes_refreshed}"
        )

        return remotes_refreshed


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
        RuntimeError: If remote reload token is not configured
    """
    remote_reload_token = settings.remote_reload_token

    if remote_reload_token is None:
        raise RuntimeError("Remote reload token not configured on server")

    return AdminService(
        remote_reload_token=remote_reload_token,
        versions_fetcher=request.app.state.versions_fetcher
    )
