"""
Tests for the Admin Service.
"""
import pytest
from unittest.mock import Mock

from web.services.admin import AdminService


class TestAdminService:
    """Test suite for AdminService business logic."""
    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Test successful token verification."""
        admin_service = AdminService(remote_reload_token="valid-token")
        result = await admin_service.verify_remote_reload_token("valid-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_failure(self):
        """Test token verification with incorrect token."""
        admin_service = AdminService(remote_reload_token="valid-token")
        result = await admin_service.verify_remote_reload_token("invalid-token")
        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_remotes_success(self, mock_versions_fetcher):
        """Test successful refresh of remote metadata."""
        admin_service = AdminService(
            remote_reload_token="some-token",
            versions_fetcher=mock_versions_fetcher
        )
        remotes = await admin_service.refresh_remotes()

        assert len(remotes) == 2
        assert "test-remote-1" in remotes
        assert "test-remote-2" in remotes

        mock_versions_fetcher.reload_remotes_json.assert_called_once()
        mock_versions_fetcher.get_all_remotes_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_remotes_empty_result(self):
        """Test refresh when no remotes are configured."""
        mock_fetcher = Mock()
        mock_fetcher.reload_remotes_json = Mock()
        mock_fetcher.get_all_remotes_info = Mock(return_value=[])

        admin_service = AdminService(
            remote_reload_token="some-token",
            versions_fetcher=mock_fetcher
        )

        remotes = await admin_service.refresh_remotes()

        assert len(remotes) == 0
        mock_fetcher.reload_remotes_json.assert_called_once()
