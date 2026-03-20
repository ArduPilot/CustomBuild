"""
Tests for the Vehicles Service.
"""
import pytest
from unittest.mock import Mock

from metadata_manager import Vehicle
from metadata_manager.versions_fetcher import VersionInfo, RemoteInfo
from web.services.vehicles import VehiclesService


@pytest.fixture
def service(mock_vehicles_manager, mock_versions_fetcher, mock_ap_src_metadata_fetcher, mock_git_repo):
    return VehiclesService(
        vehicle_manager=mock_vehicles_manager,
        versions_fetcher=mock_versions_fetcher,
        ap_src_metadata_fetcher=mock_ap_src_metadata_fetcher,
        repo=mock_git_repo,
    )


class TestVehiclesService:
    """Test suite for VehiclesService."""

    # Tests for get_all_vehicles

    def test_get_all_vehicles_returns_all(self, service, mock_vehicles_manager):
        """Test fetching all vehicles returns correct count and values."""
        mock_vehicles_manager.get_all_vehicles.return_value = [
            Vehicle(
                id="copter",
                name="Copter",
                ap_source_subdir="ArduCopter",
                fw_server_vehicle_sdir="Copter",
                waf_build_command="copter"
            ),
            Vehicle(
                id="plane",
                name="Plane",
                ap_source_subdir="ArduPlane",
                fw_server_vehicle_sdir="Plane",
                waf_build_command="plane"
            ),
        ]
        vehicles = service.get_all_vehicles()

        assert len(vehicles) == 2
        assert vehicles[0].id == "copter"
        assert vehicles[0].name == "Copter"
        assert vehicles[1].id == "plane"
        assert vehicles[1].name == "Plane"

    def test_get_all_vehicles_empty(self, service, mock_vehicles_manager):
        """Test fetching all vehicles when none exist."""
        mock_vehicles_manager.get_all_vehicles.return_value = []
        vehicles = service.get_all_vehicles()

        assert vehicles == []

    def test_get_all_vehicles_single(self, service, mock_vehicles_manager):
        """Test fetching all vehicles when only one exists."""
        mock_vehicles_manager.get_all_vehicles.return_value = [
            Vehicle(
                id="copter",
                name="Copter",
                ap_source_subdir="ArduCopter",
                fw_server_vehicle_sdir="Copter",
                waf_build_command="copter"
            ),
        ]
        vehicles = service.get_all_vehicles()

        assert len(vehicles) == 1
        assert vehicles[0].id == "copter"

    def test_get_all_vehicles_sorted_by_name(self, service, mock_vehicles_manager):
        """Test fetching all vehicles returns them sorted by name."""
        mock_vehicles_manager.get_all_vehicles.return_value = [
            Vehicle(
                id="plane",
                name="Plane",
                ap_source_subdir="ArduPlane",
                fw_server_vehicle_sdir="Plane",
                waf_build_command="plane"
            ),
            Vehicle(
                id="copter",
                name="Copter",
                ap_source_subdir="ArduCopter",
                fw_server_vehicle_sdir="Copter",
                waf_build_command="copter"
            ),
            Vehicle(
                id="rover",
                name="Rover",
                ap_source_subdir="ArduRover",
                fw_server_vehicle_sdir="Rover",
                waf_build_command="rover"
            ),
        ]
        vehicles = service.get_all_vehicles()
        names = [v.name for v in vehicles]

        assert names == sorted(names)

    def test_get_all_vehicles_calls_manager_once(self, service, mock_vehicles_manager):
        """Test that get_all_vehicles calls the manager exactly once."""
        mock_vehicles_manager.get_all_vehicles.return_value = []
        service.get_all_vehicles()

        mock_vehicles_manager.get_all_vehicles.assert_called_once_with()

    # Tests for get_vehicle

    def test_get_vehicle_found(self, service, mock_vehicles_manager):
        """Test fetching a specific vehicle that exists."""
        mock_vehicles_manager.get_vehicle_by_id.return_value = Vehicle(
            id="copter",
            name="Copter",
            ap_source_subdir="ArduCopter",
            fw_server_vehicle_sdir="Copter",
            waf_build_command="copter"
        )
        vehicle = service.get_vehicle("copter")

        assert vehicle is not None
        assert vehicle.id == "copter"
        assert vehicle.name == "Copter"

    def test_get_vehicle_not_found(self, service, mock_vehicles_manager):
        """Test fetching a specific vehicle that does not exist."""
        mock_vehicles_manager.get_vehicle_by_id.return_value = None
        vehicle = service.get_vehicle("copter")

        assert vehicle is None

    def test_get_vehicle_calls_manager_with_correct_id(self, service, mock_vehicles_manager):
        """Test that get_vehicle calls manager with the provided ID."""
        mock_vehicles_manager.get_vehicle_by_id.return_value = None
        service.get_vehicle("copter")

        mock_vehicles_manager.get_vehicle_by_id.assert_called_once_with("copter")

    # Tests for get_versions

    def test_get_versions_empty(self, service, mock_versions_fetcher):
        """Test that an empty list is returned when no versions exist."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = []
        versions = service.get_versions("copter")

        assert versions == []

    def test_get_versions_single(self, service, mock_versions_fetcher):
        """Test fetching versions when only one version exists."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter")

        assert len(versions) == 1

    def test_get_versions_many(self, service, mock_versions_fetcher):
        """Test fetching versions when multiple versions exist."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.6.0-beta",
                release_type="beta",
                version_number="4.6.0",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter")

        assert len(versions) == 3

    def test_get_versions_sorted_by_name(self, service, mock_versions_fetcher):
        """Test that versions are returned sorted by their display name."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.6.0-beta",
                release_type="beta",
                version_number="4.6.0",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter")
        names = [v.name for v in versions]

        assert names == sorted(names)

    def test_get_versions_calls_fetcher_once_with_correct_vehicle_id(
        self, service, mock_versions_fetcher
    ):
        """Test that get_versions calls the fetcher exactly once with the correct vehicle_id."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = []
        service.get_versions("copter")

        mock_versions_fetcher.get_versions_for_vehicle.assert_called_once_with(
            vehicle_id="copter"
        )

    def test_get_versions_type_filter_keeps_matching(
        self, service, mock_versions_fetcher
    ):
        """Test that type_filter returns only versions of the specified type."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.6.0-beta",
                release_type="beta",
                version_number="4.6.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter", type_filter="stable")

        assert len(versions) == 1
        assert versions[0].type == "stable"

    def test_get_versions_type_filter_excludes_non_matching(
        self, service, mock_versions_fetcher
    ):
        """Test that type_filter excludes versions that do not match."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.6.0-beta",
                release_type="beta",
                version_number="4.6.0",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter", type_filter="latest")

        assert versions == []

    def test_get_versions_type_filter_none_returns_all(
        self, service, mock_versions_fetcher
    ):
        """Test that passing no type_filter returns all versions."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.6.0-beta",
                release_type="beta",
                version_number="4.6.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter")

        assert len(versions) == 3

    def test_get_versions_type_filter_multiple_matches(
        self, service, mock_versions_fetcher
    ):
        """Test that type_filter returns all versions matching the type when there are multiple."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.4.0",
                release_type="stable",
                version_number="4.4.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter", type_filter="stable")

        assert len(versions) == 2
        assert all(v.type == "stable" for v in versions)

    def test_get_versions_latest_name_format(
        self, service, mock_versions_fetcher
    ):
        """Test that latest versions have the correct display name format."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/heads/master",
                release_type="latest",
                version_number="NA",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter")

        assert versions[0].name == "Latest (ardupilot)"

    def test_get_versions_non_latest_name_format(
        self, service, mock_versions_fetcher
    ):
        """Test that non-latest versions have the correct display name format."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
        ]
        versions = service.get_versions("copter")

        assert versions[0].name == "stable 4.5.0 (ardupilot)"

    # Tests for get_version

    def test_get_version_found(self, service, mock_versions_fetcher):
        """Test that the correct version is returned when it exists."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [version_info]

        result = service.get_version("copter", version_info.version_id)

        assert result is not None
        assert result.id == version_info.version_id

    def test_get_version_not_found(self, service, mock_versions_fetcher):
        """Test that None is returned when the version does not exist."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            VersionInfo(
                remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
                commit_ref="refs/tags/Copter-4.5.0",
                release_type="stable",
                version_number="4.5.0",
                ap_build_artifacts_url=None,
            ),
        ]

        result = service.get_version("copter", "nonexistent-version-id")

        assert result is None

    def test_get_version_no_versions_available(self, service, mock_versions_fetcher):
        """Test that None is returned when there are no versions at all."""
        mock_versions_fetcher.get_versions_for_vehicle.return_value = []

        result = service.get_version("copter", "any-version-id")

        assert result is None

    def test_get_version_returns_correct_match_among_many(self, service, mock_versions_fetcher):
        """Test that only the matching version is returned when multiple exist."""
        stable_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        beta_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.6.0-beta",
            release_type="beta",
            version_number="4.6.0",
            ap_build_artifacts_url=None,
        )
        latest_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/heads/master",
            release_type="latest",
            version_number="NA",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_versions_for_vehicle.return_value = [
            stable_info, beta_info, latest_info,
        ]

        result = service.get_version("copter", beta_info.version_id)

        assert result is not None
        assert result.id == beta_info.version_id
        assert result.type == "beta"

    # Tests for get_boards

    def test_get_boards_version_not_found_returns_empty(self, service, mock_versions_fetcher):
        """Test that an empty list is returned when the version does not exist."""
        mock_versions_fetcher.get_version_info.return_value = None

        result = service.get_boards("copter", "nonexistent-version-id")

        assert result == []

    def test_get_boards_version_info_queried_with_correct_params(
        self, service, mock_versions_fetcher
    ):
        """Test that get_version_info is called with the correct vehicle and version IDs."""
        mock_versions_fetcher.get_version_info.return_value = None

        service.get_boards("copter", "some-version-id")

        mock_versions_fetcher.get_version_info.assert_called_once_with(
            vehicle_id="copter",
            version_id="some-version-id",
        )

    def test_get_boards_empty(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that an empty list is returned when there are no boards for a version."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = []

        result = service.get_boards("copter", version_info.version_id)

        assert result == []

    def test_get_boards_single(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a single board is returned correctly."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = ["CubeRed"]

        result = service.get_boards("copter", version_info.version_id)

        assert len(result) == 1
        assert result[0].id == "CubeRed"
        assert result[0].name == "CubeRed"

    def test_get_boards_many(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that multiple boards are returned correctly."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = [
            "CubeRed", "CubeOrange", "MatekF405",
        ]

        result = service.get_boards("copter", version_info.version_id)

        assert len(result) == 3
        assert [b.id for b in result] == ["CubeRed", "CubeOrange", "MatekF405"]

    def test_get_boards_sets_correct_vehicle_and_version_ids(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that returned boards carry the correct vehicle_id and version_id."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = ["CubeRed"]

        result = service.get_boards("copter", version_info.version_id)

        assert result[0].vehicle_id == "copter"
        assert result[0].version_id == version_info.version_id

    def test_get_boards_fetcher_called_with_correct_params(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that the metadata fetcher is called with remote name, commit ref, and vehicle ID from version info."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = []

        service.get_boards("copter", version_info.version_id)

        mock_ap_src_metadata_fetcher.get_boards.assert_called_once_with(
            remote="ardupilot",
            commit_ref="refs/tags/Copter-4.5.0",
            vehicle_id="copter",
        )

    # Tests for get_board

    def test_get_board_found(self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher):
        """Test that the correct board is returned when it exists."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = ["CubeRed", "CubeOrange"]

        result = service.get_board("copter", version_info.version_id, "CubeRed")

        assert result is not None
        assert result.id == "CubeRed"
        assert result.name == "CubeRed"
        assert result.vehicle_id == "copter"
        assert result.version_id == version_info.version_id

    def test_get_board_not_found(self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher):
        """Test that None is returned when the board does not exist."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = ["CubeRed", "CubeOrange"]

        result = service.get_board("copter", version_info.version_id, "NonExistentBoard")

        assert result is None

    def test_get_board_returns_correct_match_among_many(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that only the matching board is returned when multiple boards exist."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_boards.return_value = [
            "CubeRed", "CubeOrange", "MatekF405",
        ]

        result = service.get_board("copter", version_info.version_id, "CubeOrange")

        assert result is not None
        assert result.id == "CubeOrange"

    # Tests for get_features

    def test_get_features_version_not_found_returns_empty(
        self, service, mock_versions_fetcher
    ):
        """Test that an empty list is returned when the version does not exist."""
        mock_versions_fetcher.get_version_info.return_value = None

        result = service.get_features("copter", "nonexistent-version-id", "CubeRed")

        assert result == []

    def test_get_features_zero_options_returns_empty(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that an empty list is returned when there are no build options."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = []

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result == []

    def test_get_features_one_option(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a single feature is returned correctly."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label = "HAL_LOGGING_ENABLED"
        opt.define = "HAL_LOGGING_ENABLED"
        opt.category = "Logging"
        opt.description = ""
        opt.default = 1
        opt.dependency = None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert len(result) == 1
        assert result[0].id == "HAL_LOGGING_ENABLED"
        assert result[0].name == "HAL_LOGGING_ENABLED"

    def test_get_features_many_options(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that all features are returned when multiple options exist."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_logging = Mock()
        opt_logging.label, opt_logging.define, opt_logging.category = "HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED", "Logging"
        opt_logging.description, opt_logging.default, opt_logging.dependency = "", 1, None
        opt_ekf = Mock()
        opt_ekf.label, opt_ekf.define, opt_ekf.category = "HAL_NAVEKF3_AVAILABLE", "HAL_NAVEKF3_AVAILABLE", "EKF"
        opt_ekf.description, opt_ekf.default, opt_ekf.dependency = "", 1, None
        opt_sensors = Mock()
        opt_sensors.label, opt_sensors.define, opt_sensors.category = "HAL_BEACON_ENABLED", "HAL_BEACON_ENABLED", "Sensors"
        opt_sensors.description, opt_sensors.default, opt_sensors.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_logging, opt_ekf, opt_sensors]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert len(result) == 3

    def test_get_features_sorted_by_category(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that features are sorted by category name."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_z = Mock()
        opt_z.label, opt_z.define, opt_z.category = "FEATURE_Z", "DEFINE_Z", "Sensors"
        opt_z.description, opt_z.default, opt_z.dependency = "", 1, None
        opt_a = Mock()
        opt_a.label, opt_a.define, opt_a.category = "FEATURE_A", "DEFINE_A", "EKF"
        opt_a.description, opt_a.default, opt_a.dependency = "", 1, None
        opt_m = Mock()
        opt_m.label, opt_m.define, opt_m.category = "FEATURE_M", "DEFINE_M", "Logging"
        opt_m.description, opt_m.default, opt_m.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_z, opt_a, opt_m]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert [f.category.name for f in result] == ["EKF", "Logging", "Sensors"]

    def test_get_features_uses_fallback_defaults_when_no_artifacts_url(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that build-options-py defaults are used when ap_build_artifacts_url is None."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_on = Mock()
        opt_on.label, opt_on.define, opt_on.category = "FEATURE_ON", "DEFINE_ON", "Cat"
        opt_on.description, opt_on.default, opt_on.dependency = "", 1, None
        opt_off = Mock()
        opt_off.label, opt_off.define, opt_off.category = "FEATURE_OFF", "DEFINE_OFF", "Cat"
        opt_off.description, opt_off.default, opt_off.dependency = "", 0, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_on, opt_off]

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        by_id = {f.id: f.default for f in result}
        assert by_id["FEATURE_ON"].enabled is True
        assert by_id["FEATURE_ON"].source == "build-options-py"
        assert by_id["FEATURE_OFF"].enabled is False
        assert by_id["FEATURE_OFF"].source == "build-options-py"
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.assert_not_called()

    def test_get_features_uses_firmware_server_defaults_when_available(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that firmware-server defaults override build-options-py when present."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url="https://firmware.ardupilot.org/Copter/stable-4.5.0",
        )
        opt_a = Mock()
        opt_a.label, opt_a.define, opt_a.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt_a.description, opt_a.default, opt_a.dependency = "", 1, None
        opt_b = Mock()
        opt_b.label, opt_b.define, opt_b.category = "FEATURE_B", "DEFINE_B", "Cat"
        opt_b.description, opt_b.default, opt_b.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_a, opt_b]
        # firmware server says DEFINE_A is disabled, DEFINE_B is enabled
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = {
            "DEFINE_A": 0,
            "DEFINE_B": 1,
        }

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        by_id = {f.id: f.default for f in result}
        assert by_id["FEATURE_A"].enabled is False
        assert by_id["FEATURE_A"].source == "firmware-server"
        assert by_id["FEATURE_B"].enabled is True
        assert by_id["FEATURE_B"].source == "firmware-server"

    def test_get_features_falls_back_to_defaults_when_firmware_server_returns_none(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that build-options-py fallback is used when firmware server fetch fails."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url="https://firmware.ardupilot.org/Copter/stable-4.5.0",
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt.description, opt.default, opt.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result[0].default.enabled is True
        assert result[0].default.source == "build-options-py"

    def test_get_features_firmware_server_overrides_only_known_defines(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a define absent from firmware-server data falls back to build-options-py."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url="https://firmware.ardupilot.org/Copter/stable-4.5.0",
        )
        opt_known = Mock()
        opt_known.label, opt_known.define, opt_known.category = "FEATURE_KNOWN", "DEFINE_KNOWN", "Cat"
        opt_known.description, opt_known.default, opt_known.dependency = "", 0, None
        opt_unknown = Mock()
        opt_unknown.label, opt_unknown.define, opt_unknown.category = "FEATURE_UNKNOWN", "DEFINE_UNKNOWN", "Cat"
        opt_unknown.description, opt_unknown.default, opt_unknown.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_known, opt_unknown]
        # firmware server only knows about DEFINE_KNOWN
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = {
            "DEFINE_KNOWN": 1,
        }

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        by_id = {f.id: f.default for f in result}
        assert by_id["FEATURE_KNOWN"].enabled is True
        assert by_id["FEATURE_KNOWN"].source == "firmware-server"
        assert by_id["FEATURE_UNKNOWN"].enabled is True
        assert by_id["FEATURE_UNKNOWN"].source == "build-options-py"

    def test_get_features_dependency_none(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a feature with no dependency produces an empty dependencies list."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt.description, opt.default, opt.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result[0].dependencies == []

    def test_get_features_dependency_single(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a single dependency string is parsed into a one-element list."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt.description, opt.default, opt.dependency = "", 1, "DEP_ONE"
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result[0].dependencies == ["DEP_ONE"]

    def test_get_features_dependency_multiple_comma_separated(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a comma-separated dependency string is split into multiple entries."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt.description, opt.default, opt.dependency = "", 1, "DEP_ONE,DEP_TWO,DEP_THREE"
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result[0].dependencies == ["DEP_ONE", "DEP_TWO", "DEP_THREE"]

    def test_get_features_dependency_with_spaces(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that spaces around dependency labels are stripped."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt.description, opt.default, opt.dependency = "", 1, "DEP_ONE , DEP_TWO , DEP_THREE"
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result[0].dependencies == ["DEP_ONE", "DEP_TWO", "DEP_THREE"]

    def test_get_features_ids_filled_correctly(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that vehicle_id, version_id, and board_id are correctly set on each feature."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt.description, opt.default, opt.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed")

        assert result[0].vehicle_id == "copter"
        assert result[0].version_id == version_info.version_id
        assert result[0].board_id == "CubeRed"

    def test_get_features_category_filter_keeps_matching(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that category_id filter returns only features whose category matches."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_logging = Mock()
        opt_logging.label, opt_logging.define, opt_logging.category = "HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED", "Logging"
        opt_logging.description, opt_logging.default, opt_logging.dependency = "", 1, None
        opt_ekf = Mock()
        opt_ekf.label, opt_ekf.define, opt_ekf.category = "HAL_NAVEKF3_AVAILABLE", "HAL_NAVEKF3_AVAILABLE", "EKF"
        opt_ekf.description, opt_ekf.default, opt_ekf.dependency = "", 1, None
        opt_sensors = Mock()
        opt_sensors.label, opt_sensors.define, opt_sensors.category = "HAL_BEACON_ENABLED", "HAL_BEACON_ENABLED", "Sensors"
        opt_sensors.description, opt_sensors.default, opt_sensors.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_logging, opt_ekf, opt_sensors]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed", category_id="Logging")

        assert len(result) == 1
        assert result[0].id == "HAL_LOGGING_ENABLED"
        assert result[0].category.name == "Logging"

    def test_get_features_category_filter_excludes_non_matching(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that category_id filter excludes features whose category does not match."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_logging = Mock()
        opt_logging.label, opt_logging.define, opt_logging.category = "HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED", "Logging"
        opt_logging.description, opt_logging.default, opt_logging.dependency = "", 1, None
        opt_ekf = Mock()
        opt_ekf.label, opt_ekf.define, opt_ekf.category = "HAL_NAVEKF3_AVAILABLE", "HAL_NAVEKF3_AVAILABLE", "EKF"
        opt_ekf.description, opt_ekf.default, opt_ekf.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_logging, opt_ekf]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed", category_id="Sensors")

        assert result == []

    def test_get_features_category_filter_no_matches_returns_empty(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that a category_id with no matching features returns an empty list."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_a = Mock()
        opt_a.label, opt_a.define, opt_a.category = "FEATURE_A", "DEFINE_A", "Logging"
        opt_a.description, opt_a.default, opt_a.dependency = "", 1, None
        opt_b = Mock()
        opt_b.label, opt_b.define, opt_b.category = "FEATURE_B", "DEFINE_B", "Logging"
        opt_b.description, opt_b.default, opt_b.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_a, opt_b]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_features("copter", version_info.version_id, "CubeRed", category_id="NonExistent")

        assert result == []

    # Tests for get_feature

    def test_get_feature_found(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that the correct feature is returned when it exists."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED", "Logging"
        opt.description, opt.default, opt.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_feature("copter", version_info.version_id, "CubeRed", "HAL_LOGGING_ENABLED")

        assert result is not None
        assert result.id == "HAL_LOGGING_ENABLED"
        assert result.name == "HAL_LOGGING_ENABLED"

    def test_get_feature_not_found(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that None is returned when the feature does not exist."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt = Mock()
        opt.label, opt.define, opt.category = "HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED", "Logging"
        opt.description, opt.default, opt.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_feature("copter", version_info.version_id, "CubeRed", "NONEXISTENT_FEATURE")

        assert result is None

    def test_get_feature_returns_correct_match_among_many(
        self, service, mock_versions_fetcher, mock_ap_src_metadata_fetcher
    ):
        """Test that only the matching feature is returned when multiple features exist."""
        version_info = VersionInfo(
            remote_info=RemoteInfo(name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"),
            commit_ref="refs/tags/Copter-4.5.0",
            release_type="stable",
            version_number="4.5.0",
            ap_build_artifacts_url=None,
        )
        opt_a = Mock()
        opt_a.label, opt_a.define, opt_a.category = "FEATURE_A", "DEFINE_A", "Cat"
        opt_a.description, opt_a.default, opt_a.dependency = "", 1, None
        opt_b = Mock()
        opt_b.label, opt_b.define, opt_b.category = "FEATURE_B", "DEFINE_B", "Cat"
        opt_b.description, opt_b.default, opt_b.dependency = "", 0, None
        opt_c = Mock()
        opt_c.label, opt_c.define, opt_c.category = "FEATURE_C", "DEFINE_C", "Cat"
        opt_c.description, opt_c.default, opt_c.dependency = "", 1, None
        mock_versions_fetcher.get_version_info.return_value = version_info
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt_a, opt_b, opt_c]
        mock_ap_src_metadata_fetcher.get_board_defaults_from_fw_server.return_value = None

        result = service.get_feature("copter", version_info.version_id, "CubeRed", "FEATURE_B")

        assert result is not None
        assert result.id == "FEATURE_B"
        assert result.default.enabled is False
