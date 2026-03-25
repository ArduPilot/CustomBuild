"""
Tests for the Builds API endpoints.
"""
from contextlib import contextmanager
from unittest.mock import Mock, patch, PropertyMock, MagicMock
from fastapi import status

from web.schemas import (
    BuildRequest,
    BuildSubmitResponse,
    BuildOut,
    BuildProgress,
    BuildVersionInfo,
    RemoteInfo,
)
from web.schemas.vehicles import VehicleBase, BoardBase


class TestBuildsAPI:
    """
    Tests for all Builds API endpoints.
    """

    @staticmethod
    @contextmanager
    def override_builds_service(client, mock_service):
        """Temporarily override the get_builds_service dependency."""
        from web.services.builds import get_builds_service
        client.app.dependency_overrides[get_builds_service] = lambda: mock_service
        try:
            yield
        finally:
            client.app.dependency_overrides.pop(get_builds_service, None)

    @staticmethod
    def dummy_build(build_id="build-abc123"):
        return BuildOut(
            build_id=build_id,
            vehicle=VehicleBase(id="copter", name="Copter"),
            board=BoardBase(id="MatekH743", name="MatekH743"),
            version=BuildVersionInfo(
                id="copter-4.5.0-stable",
                remote_info=RemoteInfo(
                    name="ardupilot",
                    url="https://github.com/ArduPilot/ardupilot.git",
                ),
                git_hash="abc123def456",
            ),
            selected_features=["HAL_LOGGING_ENABLED"],
            progress=BuildProgress(percent=0, state="PENDING"),
            time_created=1700000000.0,
        )

    @staticmethod
    def dummy_submit_response(build_id="build-abc123"):
        return BuildSubmitResponse(
            build_id=build_id,
            url=f"/api/v1/builds/{build_id}",
            status="submitted",
        )

    @staticmethod
    def valid_build_request_body():
        return {
            "vehicle_id": "copter",
            "board_id": "MatekH743",
            "version_id": "copter-4.5.0-stable",
            "selected_features": ["HAL_LOGGING_ENABLED"],
        }

    # POST /builds

    def test_post_build_returns_201_on_success(self, client):
        """Returns 201 Created when the build is submitted successfully."""
        mock_service = Mock()
        mock_service.create_build.return_value = self.dummy_submit_response()
        with self.override_builds_service(client, mock_service):
            response = client.post(
                "/api/v1/builds", json=self.valid_build_request_body()
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_post_build_response_schema_has_required_fields(self, client):
        """Response body contains 'build_id', 'url', and 'status'."""
        mock_service = Mock()
        mock_service.create_build.return_value = self.dummy_submit_response()
        with self.override_builds_service(client, mock_service):
            response = client.post(
                "/api/v1/builds", json=self.valid_build_request_body()
            )

        data = response.json()
        assert "build_id" in data
        assert "url" in data
        assert "status" in data
        assert data["status"] == "submitted"

    def test_post_build_returns_400_on_value_error(self, client):
        """Returns 400 when the service raises a ValueError."""
        mock_service = Mock()
        error_message = "Invalid version_id for vehicle"
        mock_service.create_build.side_effect = ValueError(error_message)
        with self.override_builds_service(client, mock_service):
            response = client.post(
                "/api/v1/builds", json=self.valid_build_request_body()
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert error_message in response.json()["detail"]

    def test_post_build_returns_422_when_required_field_missing(self, client):
        """Returns 422 when a required field is missing from the request body."""
        mock_service = Mock()
        with self.override_builds_service(client, mock_service):
            response = client.post(
                "/api/v1/builds",
                json={"vehicle_id": "copter", "board_id": "MatekH743"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_post_build_passes_request_body_to_service(self, client):
        """The parsed BuildRequest is forwarded to the service."""
        mock_service = Mock()
        mock_service.create_build.return_value = self.dummy_submit_response()
        body = self.valid_build_request_body()
        with self.override_builds_service(client, mock_service):
            client.post("/api/v1/builds", json=body)

        called_with: BuildRequest = mock_service.create_build.call_args[0][0]
        assert called_with.vehicle_id == body["vehicle_id"]
        assert called_with.board_id == body["board_id"]
        assert called_with.version_id == body["version_id"]
        assert called_with.selected_features == body["selected_features"]

    def test_post_build_selected_features_defaults_to_empty_list(self, client):
        """When 'selected_features' is omitted, an empty list is sent to the service."""
        mock_service = Mock()
        mock_service.create_build.return_value = self.dummy_submit_response()
        body = {
            "vehicle_id": "copter",
            "board_id": "MatekH743",
            "version_id": "copter-4.5.0-stable",
        }
        with self.override_builds_service(client, mock_service):
            client.post("/api/v1/builds", json=body)

        called_with: BuildRequest = mock_service.create_build.call_args[0][0]
        assert called_with.selected_features == []

    def test_post_build_rate_limit_exceed(self, client):
        """The (N+1)th POST /builds request within the window returns 429."""
        N = 10  # Rate limit is 10 requests per hour
        mock_service = Mock()
        mock_service.create_build.return_value = self.dummy_submit_response()
        with self.override_builds_service(client, mock_service):
            # Patch the request's client IP to simulate multiple requests from the same IP
            with patch(
                "starlette.requests.Request.client",
                new_callable=PropertyMock,
                return_value=MagicMock(host="192.0.2.1")
            ):
                for _ in range(N):
                    response = client.post(
                        "/api/v1/builds",
                        json=self.valid_build_request_body(),
                    )
                    assert response.status_code == status.HTTP_201_CREATED

                response = client.post(
                    "/api/v1/builds",
                    json=self.valid_build_request_body(),
                )
                assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

            # A different IP should still be able to make requests successfully
            with patch(
                "starlette.requests.Request.client",
                new_callable=PropertyMock,
                return_value=MagicMock(host="192.0.2.2")
            ):
                response = client.post(
                    "/api/v1/builds",
                    json=self.valid_build_request_body(),
                )
                assert response.status_code == status.HTTP_201_CREATED

    def test_builds_endpoint_methods_not_allowed(self, client):
        """Only POST and GET are allowed on /builds"""
        for method in [client.put, client.patch, client.delete]:
            response = method("/api/v1/builds")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /builds

    def test_list_builds_returns_200_with_build_list(self, client):
        """Returns 200 and a list of builds."""
        mock_service = Mock()
        mock_service.list_builds.return_value = [
            self.dummy_build("build-1"),
            self.dummy_build("build-2"),
        ]
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]
        assert len(response.json()) == 2

    def test_list_builds_returns_200_with_empty_list(self, client):
        """Returns 200 with an empty list when no builds exist."""
        mock_service = Mock()
        mock_service.list_builds.return_value = []
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_builds_response_schema_has_required_fields(self, client):
        """Each build in the response has the required schema fields."""
        mock_service = Mock()
        mock_service.list_builds.return_value = [self.dummy_build()]
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds")

        data = response.json()
        build = data[0]
        for field in [
            "build_id", "vehicle", "board", "version",
            "selected_features", "progress", "time_created",
        ]:
            assert field in build
        assert "id" in build["vehicle"] and "name" in build["vehicle"]
        assert "id" in build["board"] and "name" in build["board"]
        assert "id" in build["version"]
        assert "percent" in build["progress"] and "state" in build["progress"]

    def test_list_builds_no_query_params_passes_defaults_to_service(self, client):
        """Without query params, defaults are forwarded to the service."""
        mock_service = Mock()
        mock_service.list_builds.return_value = []
        with self.override_builds_service(client, mock_service):
            client.get("/api/v1/builds")

        mock_service.list_builds.assert_called_once_with(
            vehicle_id=None,
            board_id=None,
            state=None,
            limit=20,
            offset=0,
        )

    def test_list_builds_all_filters_forwarded_to_service(self, client):
        """All query params are forwarded together correctly."""
        mock_service = Mock()
        mock_service.list_builds.return_value = []
        with self.override_builds_service(client, mock_service):
            client.get(
                "/api/v1/builds?vehicle_id=copter&board_id=CubeOrange&state=RUNNING&limit=10&offset=5"
            )

        mock_service.list_builds.assert_called_once_with(
            vehicle_id="copter",
            board_id="CubeOrange",
            state="RUNNING",
            limit=10,
            offset=5,
        )

    def test_list_builds_invalid_limit_returns_422(self, client):
        """A limit below the minimum (1) returns 422."""
        mock_service = Mock()
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds?limit=0")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_builds_invalid_offset_returns_422(self, client):
        """A negative offset returns 422."""
        mock_service = Mock()
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds?offset=-1")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # GET /builds/{build_id}

    def test_get_build_returns_200_when_found(self, client):
        """Returns 200 when the build exists."""
        mock_service = Mock()
        mock_service.get_build.return_value = self.dummy_build("build-abc123")
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/build-abc123")

        assert response.status_code == status.HTTP_200_OK

    def test_get_build_returns_404_when_not_found(self, client):
        """Returns 404 when the service returns None."""
        mock_service = Mock()
        mock_service.get_build.return_value = None
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/some-build-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "some-build-id" in response.json()["detail"]

    def test_get_build_response_schema_has_required_fields(self, client):
        """Response body matches BuildOut schema."""
        mock_service = Mock()
        mock_service.get_build.return_value = self.dummy_build()
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/build-abc123")

        data = response.json()
        for field in [
            "build_id", "vehicle", "board", "version",
            "selected_features", "progress", "time_created",
        ]:
            assert field in data

    def test_get_build_service_called_with_correct_build_id(self, client):
        """The build_id path param is forwarded to the service."""
        mock_service = Mock()
        mock_service.get_build.return_value = self.dummy_build("build-xyz")
        with self.override_builds_service(client, mock_service):
            client.get("/api/v1/builds/build-xyz")

        mock_service.get_build.assert_called_once_with("build-xyz")

    def test_get_build_method_not_allowed(self, client):
        """Non-GET methods on /builds/{build_id} return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/builds/build-abc123")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /builds/{build_id}/logs

    def test_get_build_logs_returns_200_when_available(self, client):
        """Returns 200 with plain-text logs when available."""
        mock_service = Mock()
        mock_service.get_build_logs.return_value = "line1\nline2\nline3"
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/build-abc123/logs")

        assert response.status_code == status.HTTP_200_OK
        assert "text/plain" in response.headers["content-type"]

    def test_get_build_logs_response_is_plain_text(self, client):
        """Logs endpoint returns the log content as plain text."""
        mock_service = Mock()
        mock_service.get_build_logs.return_value = "some log output"
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/build-abc123/logs")

        assert response.text == "some log output"

    def test_get_build_logs_returns_404_when_not_available(self, client):
        """Returns 404 when logs are not available (service returns None)."""
        mock_service = Mock()
        mock_service.get_build_logs.return_value = None
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/some-build-id/logs")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "some-build-id" in response.json()["detail"]

    def test_get_build_logs_tail_query_param_forwarded_to_service(self, client):
        """The 'tail' query param is forwarded to the service."""
        mock_service = Mock()
        mock_service.get_build_logs.return_value = "last 10 lines"
        with self.override_builds_service(client, mock_service):
            client.get("/api/v1/builds/build-abc123/logs?tail=10")

        mock_service.get_build_logs.assert_called_once_with("build-abc123", 10)

    def test_get_build_logs_no_tail_passes_none_to_service(self, client):
        """When 'tail' is absent, None is passed to the service."""
        mock_service = Mock()
        mock_service.get_build_logs.return_value = "all logs"
        with self.override_builds_service(client, mock_service):
            client.get("/api/v1/builds/build-abc123/logs")

        mock_service.get_build_logs.assert_called_once_with("build-abc123", None)

    def test_get_build_logs_invalid_tail_returns_422(self, client):
        """A tail value below the minimum (1) returns 422."""
        mock_service = Mock()
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/build-abc123/logs?tail=0")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_build_logs_service_called_with_correct_build_id(self, client):
        """The build_id path param is forwarded to the service for logs."""
        mock_service = Mock()
        mock_service.get_build_logs.return_value = "logs"
        with self.override_builds_service(client, mock_service):
            client.get("/api/v1/builds/specific-build/logs")

        mock_service.get_build_logs.assert_called_once_with("specific-build", None)

    def test_get_build_logs_method_not_allowed(self, client):
        """Non-GET methods on /builds/{build_id}/logs return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/builds/build-abc123/logs")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /builds/{build_id}/artifact

    def test_get_artifact_returns_200_when_available(self, client, tmp_path):
        """Returns 200 with a file download when the artifact exists."""
        artifact = tmp_path / "build-abc123.tar.gz"
        artifact.write_bytes(b"fake firmware binary content")
        mock_service = Mock()
        mock_service.get_artifact_path.return_value = str(artifact)
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/build-abc123/artifact")

        assert response.status_code == status.HTTP_200_OK

    def test_get_artifact_returns_404_when_not_available(self, client):
        """Returns 404 when the artifact is not available (service returns None)."""
        mock_service = Mock()
        mock_service.get_artifact_path.return_value = None
        with self.override_builds_service(client, mock_service):
            response = client.get("/api/v1/builds/some-build-id/artifact")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "some-build-id" in response.json()["detail"]

    def test_get_artifact_service_called_with_correct_build_id(self, client):
        """The build_id path param is forwarded to the service for artifact download."""
        mock_service = Mock()
        mock_service.get_artifact_path.return_value = None
        with self.override_builds_service(client, mock_service):
            client.get("/api/v1/builds/target-build/artifact")

        mock_service.get_artifact_path.assert_called_once_with("target-build")

    def test_get_artifact_method_not_allowed(self, client):
        """Non-GET methods on /builds/{build_id}/artifact return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/builds/build-abc123/artifact")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
