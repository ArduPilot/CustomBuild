"""
Tests for the Vehicles API endpoints.
"""
from contextlib import contextmanager
from unittest.mock import Mock
from fastapi import status

from web.schemas import (
    VehicleBase,
    VersionOut,
    BoardOut,
    FeatureOut,
    CategoryBase,
    FeatureDefault,
    RemoteInfo,
)


class TestVehiclesAPI:
    """
    Tests for all Vehicles API endpoints.
    """

    @staticmethod
    @contextmanager
    def override_vehicles_service(client, mock_service):
        """Temporarily override the get_vehicles_service dependency."""
        from web.services.vehicles import get_vehicles_service
        client.app.dependency_overrides[get_vehicles_service] = lambda: mock_service
        try:
            yield
        finally:
            client.app.dependency_overrides.pop(get_vehicles_service, None)

    @staticmethod
    def dummy_version():
        return VersionOut(
            id="copter-4.5.0-stable",
            name="stable 4.5.0 (ardupilot)",
            type="stable",
            remote=RemoteInfo(
                name="ardupilot",
                url="https://github.com/ArduPilot/ardupilot.git"
            ),
            commit_ref="refs/tags/Copter-4.5.0",
            vehicle_id="copter",
        )

    @staticmethod
    def dummy_board(
        vehicle_id="copter",
        version_id="copter-4.5.0-stable",
        board_id="MatekH743",
    ):
        return BoardOut(
            id=board_id,
            name=board_id,
            vehicle_id=vehicle_id,
            version_id=version_id,
        )

    @staticmethod
    def dummy_feature(
        vehicle_id="copter",
        version_id="copter-4.5.0-stable",
        board_id="MatekH743",
        feature_id="FEATURE_A",
    ):
        return FeatureOut(
            id=feature_id,
            name="Feature A",
            category=CategoryBase(id="cat1", name="Category 1"),
            description="A test feature",
            vehicle_id=vehicle_id,
            version_id=version_id,
            board_id=board_id,
            default=FeatureDefault(enabled=True, source="build-options-py"),
            dependencies=[],
        )

    # GET /vehicles

    def test_list_vehicles_returns_200_with_vehicle_list(self, client):
        """Returns 200 and a list of vehicles when service has data."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_all_vehicles.return_value = [
            VehicleBase(id="copter", name="Copter"),
            VehicleBase(id="plane", name="Plane"),
        ]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_list_vehicles_returns_200_with_empty_list(self, client):
        """Returns 200 with an empty list when no vehicles are available."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_all_vehicles.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_vehicles_response_schema_has_required_fields(self, client):
        """Each vehicle in the response has 'id' and 'name' fields."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_all_vehicles.return_value = [
            VehicleBase(id="copter", name="Copter"),
        ]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles")

        data = response.json()
        assert len(data) == 1
        assert "id" in data[0]
        assert "name" in data[0]

    def test_list_vehicles_method_not_allowed(self, client):
        """Non-GET methods on /vehicles return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/vehicles")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}

    def test_get_vehicle_returns_200_when_found(self, client):
        """Returns 200 when the vehicle exists."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_vehicle.return_value = VehicleBase(id="copter", name="Copter")
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter")

        assert response.status_code == status.HTTP_200_OK

    def test_get_vehicle_returns_404_when_not_found(self, client):
        """Returns 404 when the service returns None."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_vehicle.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/unknown")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_vehicle_404_detail_contains_vehicle_id(self, client):
        """The 404 error detail mentions the requested vehicle ID."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_vehicle.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/some-vehicle-id")

        assert "some-vehicle-id" in response.json()["detail"]

    def test_get_vehicle_response_schema_has_required_fields(self, client):
        """Response body contains 'id' and 'name'."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_vehicle.return_value = VehicleBase(id="copter", name="Copter")
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter")

        data = response.json()
        assert data["id"] == "copter"
        assert data["name"] == "Copter"

    def test_get_vehicle_service_called_with_correct_vehicle_id(self, client):
        """The vehicle_id path param is forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_vehicle.return_value = VehicleBase(id="plane", name="Plane")
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get("/api/v1/vehicles/plane")

        mock_vehicles_service.get_vehicle.assert_called_once_with("plane")

    def test_get_vehicle_method_not_allowed(self, client):
        """Non-GET methods on /vehicles/{vehicle_id} return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/vehicles/copter")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}/versions

    def test_list_versions_returns_200_with_version_list(self, client):
        """Returns 200 and a list of versions."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_versions.return_value = [self.dummy_version()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_list_versions_returns_200_with_empty_list(self, client):
        """Returns 200 with an empty list when no versions exist."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_versions.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_versions_response_schema_has_required_fields(self, client):
        """Each version in the response has the required schema fields."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_versions.return_value = [self.dummy_version()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions")

        data = response.json()
        assert len(data) == 1
        version = data[0]
        for field in ["id", "name", "type", "remote", "commit_ref", "vehicle_id"]:
            assert field in version
        assert "name" in version["remote"]
        assert "url" in version["remote"]

    def test_list_versions_type_query_param_forwarded_to_service(self, client):
        """The 'type' query param is passed as type_filter to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_versions.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get("/api/v1/vehicles/copter/versions?type=stable")

        mock_vehicles_service.get_versions.assert_called_once_with(
            "copter", type_filter="stable"
        )

    def test_list_versions_no_type_query_param_passes_none_to_service(self, client):
        """When 'type' is absent, type_filter=None is passed to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_versions.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get("/api/v1/vehicles/copter/versions")

        mock_vehicles_service.get_versions.assert_called_once_with(
            "copter", type_filter=None
        )

    def test_list_versions_vehicle_id_forwarded_to_service(self, client):
        """The vehicle_id path param is forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_versions.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get("/api/v1/vehicles/plane/versions")

        mock_vehicles_service.get_versions.assert_called_once_with(
            "plane", type_filter=None
        )

    def test_list_versions_method_not_allowed(self, client):
        """Non-GET methods on /vehicles/{vehicle_id}/versions return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/vehicles/copter/versions")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}/versions/{version_id}

    def test_get_version_returns_200_when_found(self, client):
        """Returns 200 when the version exists."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_version.return_value = self.dummy_version()
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable")

        assert response.status_code == status.HTTP_200_OK

    def test_get_version_returns_404_when_not_found(self, client):
        """Returns 404 when the service returns None."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_version.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_version_404_detail_contains_vehicle_and_version_id(self, client):
        """The 404 error detail mentions both the vehicle ID and version ID."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_version.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/nonexistent")

        detail = response.json()["detail"]
        assert "copter" in detail
        assert "nonexistent" in detail

    def test_get_version_response_schema_has_required_fields(self, client):
        """Response body matches VersionOut schema."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_version.return_value = self.dummy_version()
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable")

        data = response.json()
        for field in ["id", "name", "type", "remote", "commit_ref", "vehicle_id"]:
            assert field in data

    def test_get_version_service_called_with_correct_ids(self, client):
        """Both vehicle_id and version_id are forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_version.return_value = self.dummy_version()
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable")

        mock_vehicles_service.get_version.assert_called_once_with(
            "copter", "copter-4.5.0-stable"
        )

    def test_get_version_method_not_allowed(self, client):
        """Non-GET methods on /vehicles/{vehicle_id}/versions/{version_id} return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/vehicles/copter/versions/v1")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}/versions/{version_id}/boards

    def test_list_boards_returns_200_when_boards_exist(self, client):
        """Returns 200 and a list of boards when boards are available."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_boards.return_value = [self.dummy_board()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_list_boards_returns_404_when_no_boards(self, client):
        """Returns 404 (not 200) when service returns an empty list."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_boards.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_boards_404_detail_contains_vehicle_and_version_id(self, client):
        """The 404 error detail mentions both the vehicle ID and version ID."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_boards.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards")

        detail = response.json()["detail"]
        assert "copter" in detail
        assert "copter-4.5.0-stable" in detail

    def test_list_boards_response_schema_has_required_fields(self, client):
        """Each board in the response has the required schema fields."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_boards.return_value = [self.dummy_board()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards")

        data = response.json()
        assert len(data) == 1
        board = data[0]
        for field in ["id", "name", "vehicle_id", "version_id"]:
            assert field in board

    def test_list_boards_service_called_with_correct_ids(self, client):
        """Both vehicle_id and version_id are forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_boards.return_value = [self.dummy_board()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get("/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards")

        mock_vehicles_service.get_boards.assert_called_once_with(
            "copter", "copter-4.5.0-stable"
        )

    def test_list_boards_method_not_allowed(self, client):
        """Non-GET methods on .../boards return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/vehicles/copter/versions/v1/boards")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}/versions/{version_id}/boards/{board_id}

    def test_get_board_returns_200_when_found(self, client):
        """Returns 200 when the board exists."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_board.return_value = self.dummy_board()
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(
                "/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards/MatekH743"
            )

        assert response.status_code == status.HTTP_200_OK

    def test_get_board_returns_404_when_not_found(self, client):
        """Returns 404 when the service returns None."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_board.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(
                "/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards/unknown"
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_board_404_detail_contains_board_id(self, client):
        """The 404 error detail mentions the requested board ID."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_board.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(
                "/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards/unknown"
            )

        assert "unknown" in response.json()["detail"]

    def test_get_board_response_schema_has_required_fields(self, client):
        """Response body matches BoardOut schema."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_board.return_value = self.dummy_board()
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(
                "/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards/MatekH743"
            )

        data = response.json()
        for field in ["id", "name", "vehicle_id", "version_id"]:
            assert field in data

    def test_get_board_service_called_with_correct_ids(self, client):
        """All three path params are forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_board.return_value = self.dummy_board()
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get(
                "/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards/MatekH743"
            )

        mock_vehicles_service.get_board.assert_called_once_with(
            "copter", "copter-4.5.0-stable", "MatekH743"
        )

    def test_get_board_method_not_allowed(self, client):
        """Non-GET methods on .../boards/{board_id} return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method("/api/v1/vehicles/copter/versions/v1/boards/b1")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}/versions/{version_id}/boards/{board_id}/features

    _FEATURES_URL = "/api/v1/vehicles/copter/versions/copter-4.5.0-stable/boards/MatekH743/features"

    def test_list_features_returns_200_with_feature_list(self, client):
        """Returns 200 and a list of features."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_features.return_value = [self.dummy_feature()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(self._FEATURES_URL)

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_list_features_returns_200_with_empty_list(self, client):
        """Returns 200 with empty list (unlike boards, empty features is not a 404)."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_features.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(self._FEATURES_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_features_response_schema_has_required_fields(self, client):
        """Each feature in the response has the required schema fields."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_features.return_value = [self.dummy_feature()]
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(self._FEATURES_URL)

        data = response.json()
        assert len(data) == 1
        feature = data[0]
        for field in ["id", "name", "category", "vehicle_id", "version_id", "board_id", "default", "dependencies"]:
            assert field in feature
        assert "enabled" in feature["default"]
        assert "source" in feature["default"]

    def test_list_features_category_id_query_param_forwarded_to_service(self, client):
        """The 'category_id' query param is forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_features.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get(self._FEATURES_URL + "?category_id=cat1")

        mock_vehicles_service.get_features.assert_called_once_with(
            "copter", "copter-4.5.0-stable", "MatekH743", "cat1"
        )

    def test_list_features_no_category_id_passes_none_to_service(self, client):
        """When 'category_id' is absent, None is passed to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_features.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get(self._FEATURES_URL)

        mock_vehicles_service.get_features.assert_called_once_with(
            "copter", "copter-4.5.0-stable", "MatekH743", None
        )

    def test_list_features_service_called_with_correct_path_params(self, client):
        """All three path params are forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_features.return_value = []
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get(
                "/api/v1/vehicles/plane/versions/plane-4.4.0-stable/boards/CubeOrange/features"
            )

        mock_vehicles_service.get_features.assert_called_once_with(
            "plane", "plane-4.4.0-stable", "CubeOrange", None
        )

    def test_list_features_method_not_allowed(self, client):
        """Non-GET methods on .../features return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method(self._FEATURES_URL)
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # GET /vehicles/{vehicle_id}/versions/{version_id}/boards/{board_id}/features/{feature_id}

    def test_get_feature_returns_200_when_found(self, client):
        """Returns 200 when the feature exists."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_feature.return_value = self.dummy_feature()
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(f"{self._FEATURES_URL}/FEATURE_A")

        assert response.status_code == status.HTTP_200_OK

    def test_get_feature_returns_404_when_not_found(self, client):
        """Returns 404 when the service returns None."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_feature.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(f"{self._FEATURES_URL}/UNKNOWN_FEATURE")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_feature_404_detail_contains_feature_id(self, client):
        """The 404 error detail mentions the requested feature ID."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_feature.return_value = None
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(f"{self._FEATURES_URL}/UNKNOWN_FEATURE")

        assert "UNKNOWN_FEATURE" in response.json()["detail"]

    def test_get_feature_response_schema_has_required_fields(self, client):
        """Response body matches FeatureOut schema."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_feature.return_value = self.dummy_feature()
        with self.override_vehicles_service(client, mock_vehicles_service):
            response = client.get(f"{self._FEATURES_URL}/FEATURE_A")

        data = response.json()
        for field in ["id", "name", "category", "vehicle_id", "version_id", "board_id", "default", "dependencies"]:
            assert field in data

    def test_get_feature_service_called_with_correct_ids(self, client):
        """All four path params are forwarded to the service."""
        mock_vehicles_service = Mock()
        mock_vehicles_service.get_feature.return_value = self.dummy_feature()
        with self.override_vehicles_service(client, mock_vehicles_service):
            client.get(f"{self._FEATURES_URL}/FEATURE_A")

        mock_vehicles_service.get_feature.assert_called_once_with(
            "copter", "copter-4.5.0-stable", "MatekH743", "FEATURE_A"
        )

    def test_get_feature_method_not_allowed(self, client):
        """Non-GET methods on .../features/{feature_id} return 405."""
        for method in [client.post, client.put, client.patch, client.delete]:
            response = method(f"{self._FEATURES_URL}/FEATURE_A")
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
