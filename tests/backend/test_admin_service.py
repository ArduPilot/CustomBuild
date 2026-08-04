"""
Tests for the Admin Service.
"""
import pytest
from unittest.mock import Mock

from backend.services.admin import AdminService


class TestAdminService:
    """Test suite for AdminService business logic."""
    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Test successful token verification."""
        admin_service = AdminService(admin_token="valid-token")
        result = await admin_service.verify_admin_token("valid-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_failure(self):
        """Test token verification with incorrect token."""
        admin_service = AdminService(admin_token="valid-token")
        result = await admin_service.verify_admin_token("invalid-token")
        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_versions_success(self, mock_versions_manager):
        """Test successful refresh of version metadata."""
        admin_service = AdminService(
            admin_token="some-token",
            versions_manager=mock_versions_manager
        )
        remotes = await admin_service.refresh_versions()

        assert len(remotes) == 2
        assert "test-remote-1" in remotes
        assert "test-remote-2" in remotes

        mock_versions_manager.refresh_all.assert_called_once()
        mock_versions_manager.get_all_remotes_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_versions_empty_result(self):
        """Test refresh when no remotes are configured."""
        mock_fetcher = Mock()
        mock_fetcher.refresh_all = Mock()
        mock_fetcher.get_all_remotes_info = Mock(return_value=[])

        admin_service = AdminService(
            admin_token="some-token",
            versions_manager=mock_fetcher
        )

        remotes = await admin_service.refresh_versions()

        assert len(remotes) == 0
        mock_fetcher.refresh_all.assert_called_once()
