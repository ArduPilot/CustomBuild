"""
Admin service for handling administrative operations.
"""
import logging
from typing import Optional, List

from fastapi import Request

from core.config import get_settings

logger = logging.getLogger(__name__)


class AdminService:
    """Service for managing administrative operations."""

    def __init__(self, versions_fetcher=None):
        """
        Initialize the admin service.

        Args:
            versions_fetcher: VersionsFetcher instance for managing remotes
        """
        self.versions_fetcher = versions_fetcher
        self.settings = get_settings()

    def get_auth_token(self) -> Optional[str]:
        """
        Retrieve the authorization token from file or environment.

        Returns:
            The authorization token if found, None otherwise
        """
        try:
            # Try to read the secret token from the file
            token_file_path = self.settings.admin_token_file_path
            with open(token_file_path, 'r') as file:
                token = file.read().strip()
                return token
        except (FileNotFoundError, PermissionError) as e:
            logger.error(
                f"Couldn't open token file at "
                f"{self.settings.admin_token_file_path}: {e}. "
                "Checking environment for token."
            )
            # If the file does not exist or no permission, check environment
            return self.settings.admin_token_env
        except Exception as e:
            logger.error(
                f"Unexpected error reading token file at "
                f"{self.settings.admin_token_file_path}: {e}. "
                "Checking environment for token."
            )
            # For any other error, fall back to environment variable
            return self.settings.admin_token_env

    async def verify_token(self, token: str) -> bool:
        """
        Verify that the provided token matches the expected admin token.

        Args:
            token: The token to verify

        Returns:
            True if token is valid, False otherwise

        Raises:
            RuntimeError: If admin token is not configured on server
        """
        expected_token = self.get_auth_token()

        if expected_token is None:
            logger.error("No admin token configured")
            raise RuntimeError("Admin token not configured on server")

        return token == expected_token

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


def get_admin_service(request: Request) -> AdminService:
    """
    Get AdminService instance with dependencies from app state.

    Args:
        request: FastAPI Request object

    Returns:
        AdminService instance initialized with app state dependencies
    """
    return AdminService(versions_fetcher=request.app.state.versions_fetcher)
