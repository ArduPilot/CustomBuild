"""
End-to-end tests for the Admin API endpoints.
"""
from contextlib import contextmanager
from unittest.mock import Mock

from fastapi import status

from web.core.config import get_settings


class TestAdminRefreshRemotesEndpoint:
    """Test suite for the /admin/refresh_remotes endpoint."""

    AUTH_HEADERS = {"Authorization": "Bearer test-remote-reload-token-12345"}
    TEST_TOKEN = "test-remote-reload-token-12345"

    @staticmethod
    @contextmanager
    def override_settings(client, mock_settings):
        """override get_settings with the provided mock."""
        client.app.dependency_overrides[get_settings] = lambda: mock_settings
        try:
            yield
        finally:
            client.app.dependency_overrides.pop(get_settings, None)

    def test_refresh_remotes_success(self, client, test_base_dir):
        """Test successful refresh of remotes with valid auth and verifies against remotes.json."""
        import os
        import json

        remotes_file = os.path.join(test_base_dir, "configs", "remotes.json")
        assert os.path.exists(remotes_file)

        with open(remotes_file, "r") as f:
            initial_remotes = json.load(f)

        mock_settings = Mock()
        mock_settings.remote_reload_token = self.TEST_TOKEN
        with self.override_settings(client, mock_settings):
            response = client.post(
                "/api/v1/admin/refresh_remotes",
                headers=self.AUTH_HEADERS
            )

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

        data = response.json()

        assert len(data["remotes"]) == len(initial_remotes)
        expected_names = [r["name"] for r in initial_remotes]
        for name in expected_names:
            assert name in data["remotes"]

    def test_refresh_remotes_no_auth(self, client):
        """Test refresh without authentication - should fail."""
        mock_settings = Mock()
        mock_settings.remote_reload_token = self.TEST_TOKEN
        with self.override_settings(client, mock_settings):
            response = client.post("/api/v1/admin/refresh_remotes")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_remotes_invalid_token(self, client):
        """Test refresh with invalid token - should fail."""
        mock_settings = Mock()
        mock_settings.remote_reload_token = self.TEST_TOKEN
        with self.override_settings(client, mock_settings):
            response = client.post(
                "/api/v1/admin/refresh_remotes",
                headers={"Authorization": "Bearer invalid-token-xyz"}
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        data = response.json()
        assert "detail" in data
        assert "Invalid authentication token" in data["detail"]

    def test_refresh_remotes_malformed_auth_header(self, client):
        """Test refresh with malformed authorization header."""
        mock_settings = Mock()
        mock_settings.remote_reload_token = self.TEST_TOKEN
        with self.override_settings(client, mock_settings):
            response = client.post(
                "/api/v1/admin/refresh_remotes",
                headers={"Authorization": "test-remote-reload-token-12345"}
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_remotes_empty_token(self, client):
        """Test refresh with empty token."""
        mock_settings = Mock()
        mock_settings.remote_reload_token = self.TEST_TOKEN
        with self.override_settings(client, mock_settings):
            response = client.post(
                "/api/v1/admin/refresh_remotes",
                headers={"Authorization": "Bearer "}
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_remotes_method_not_allowed(self, client):
        """Test that only POST method is allowed."""
        disallowed_methods = [
            ("GET", client.get),
            ("PUT", client.put),
            ("PATCH", client.patch),
            ("DELETE", client.delete),
        ]

        mock_settings = Mock()
        mock_settings.remote_reload_token = self.TEST_TOKEN
        with self.override_settings(client, mock_settings):
            for method_name, method_func in disallowed_methods:
                response = method_func(
                    "/api/v1/admin/refresh_remotes",
                    headers=self.AUTH_HEADERS
                )
                assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED, \
                    f"{method_name} should return 405"
