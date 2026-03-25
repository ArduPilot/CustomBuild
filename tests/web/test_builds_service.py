"""
Tests for the Builds Service.
"""
import time
import pytest
from unittest.mock import Mock, MagicMock

import build_manager as bm
from metadata_manager import RemoteInfo as ManagerRemoteInfo
from metadata_manager.versions_fetcher import RemoteInfo, VersionInfo
from web.schemas import BuildRequest
from web.services.builds import BuildsService


@pytest.fixture
def service(
    mock_build_manager,
    mock_versions_fetcher,
    mock_ap_src_metadata_fetcher,
    mock_git_repo,
    mock_vehicles_manager,
):
    """Create a BuildsService instance with mocked dependencies."""
    mock_versions_fetcher.get_version_info.return_value = make_version_info()
    mock_versions_fetcher.get_remote_info.return_value = RemoteInfo(
        name="ardupilot", url="https://github.com/ArduPilot/ardupilot.git"
    )
    mock_ap_src_metadata_fetcher.get_boards.return_value = ["MatekH743", "CubeOrange"]
    mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = []
    mock_git_repo.commit_id_for_remote_ref.return_value = "abc123def456"
    mock_git_repo.get_checkout_lock.return_value = MagicMock()
    mock_build_manager.submit_build.return_value = "new-build-id"
    mock_copter, mock_plane, mock_rover = Mock(), Mock(), Mock()
    mock_copter.name, mock_plane.name, mock_rover.name = "Copter", "Plane", "Rover"
    mock_copter.id, mock_plane.id, mock_rover.id = "copter", "plane", "rover"
    vehicles = {"copter": mock_copter, "plane": mock_plane, "rover": mock_rover}
    mock_vehicles_manager.get_vehicle_by_id = Mock(
        side_effect=lambda vid: vehicles.get(vid)
    )
    mock_vehicles_manager.get_vehicle_names = Mock(return_value=[v.name for v in vehicles.values()])

    return BuildsService(
        build_manager=mock_build_manager,
        versions_fetcher=mock_versions_fetcher,
        ap_src_metadata_fetcher=mock_ap_src_metadata_fetcher,
        repo=mock_git_repo,
        vehicles_manager=mock_vehicles_manager,
    )


def make_version_info(
    remote_name="ardupilot",
    remote_url="https://github.com/ArduPilot/ardupilot.git",
    commit_ref="refs/tags/Copter-4.5.0",
    release_type="stable",
    version_number="4.5.0",
    ap_build_artifacts_url=None,
):
    return VersionInfo(
        remote_info=RemoteInfo(name=remote_name, url=remote_url),
        commit_ref=commit_ref,
        release_type=release_type,
        version_number=version_number,
        ap_build_artifacts_url=ap_build_artifacts_url,
    )


def make_build_info(
    vehicle_id="copter",
    version_id="copter-4.5.0-stable",
    remote_name="ardupilot",
    remote_url="https://github.com/ArduPilot/ardupilot.git",
    git_hash="abc123def456",
    board="MatekH743",
    selected_features=None,
    state=bm.BuildState.PENDING,
    percent=0,
):
    info = bm.BuildInfo(
        vehicle_id=vehicle_id,
        version_id=version_id,
        remote_info=ManagerRemoteInfo(name=remote_name, url=remote_url),
        git_hash=git_hash,
        board=board,
        selected_features=selected_features or set(),
    )
    info.progress = bm.BuildProgress(state=state, percent=percent)
    return info


class TestBuildsService:
    """Test suite for BuildsService."""

    @staticmethod
    def setup_builds(
        mock_build_manager,
        build_infos,
    ):
        """Populate mock build_manager with the given BuildInfo objects."""
        ids = [f"build-{i}" for i in range(len(build_infos))]
        mock_build_manager.get_all_build_ids.return_value = ids
        mock_build_manager.get_build_info.side_effect = lambda bid: (
            build_infos[ids.index(bid)]
        )

    # Tests for create_build

    def test_create_build_returns_submit_response(
        self,
        service,
    ):
        """A valid request returns a BuildSubmitResponse with build_id and url."""
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="copter-4.5.0-stable",
            selected_features=[],
        )

        result = service.create_build(request)

        assert result.build_id == "new-build-id"
        assert result.url == "/api/v1/builds/new-build-id"
        assert result.status == "submitted"

    def test_create_build_calls_submit_build_once(
        self,
        service,
        mock_build_manager,
    ):
        """submit_build is called exactly once per create_build invocation."""
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="copter-4.5.0-stable",
            selected_features=[],
        )

        service.create_build(request)

        mock_build_manager.submit_build.assert_called_once()

    def test_create_build_raises_value_error_for_missing_version_id(self, service):
        """ValueError is raised when version_id is an empty string."""
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="",
            selected_features=[],
        )

        with pytest.raises(ValueError, match="version_id is required"):
            service.create_build(request)

    def test_create_build_raises_value_error_for_missing_vehicle_id(self, service):
        """ValueError is raised when vehicle_id is an empty string."""
        request = BuildRequest(
            vehicle_id="",
            board_id="MatekH743",
            version_id="copter-4.5.0-stable",
            selected_features=[],
        )

        with pytest.raises(ValueError, match="vehicle_id is required"):
            service.create_build(request)

    def test_create_build_raises_value_error_for_missing_board_id(
        self, service
    ):
        """ValueError is raised when board_id is an empty string."""
        request = BuildRequest(
            vehicle_id="copter",
            board_id="",
            version_id="copter-4.5.0-stable",
            selected_features=[],
        )

        with pytest.raises(ValueError, match="board_id is required"):
            service.create_build(request)

    def test_create_build_raises_value_error_for_invalid_version(
        self, service, mock_versions_fetcher
    ):
        """ValueError is raised when the version_id is not found."""
        mock_versions_fetcher.get_version_info.return_value = None
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="nonexistent-version",
            selected_features=[],
        )

        with pytest.raises(ValueError, match="Invalid version_id for vehicle"):
            service.create_build(request)

    def test_create_build_queries_version_info_with_correct_params(
        self, service, mock_versions_fetcher
    ):
        """get_version_info is called with the correct vehicle_id and version_id."""
        mock_versions_fetcher.get_version_info.return_value = None
        request = BuildRequest(
            vehicle_id="plane",
            board_id="CubeOrange",
            version_id="plane-4.4.0-stable",
            selected_features=[],
        )

        with pytest.raises(ValueError):
            service.create_build(request)

        mock_versions_fetcher.get_version_info.assert_called_once_with(
            vehicle_id="plane",
            version_id="plane-4.4.0-stable",
        )

    def test_create_build_raises_value_error_when_remote_not_found(
        self, service, mock_versions_fetcher
    ):
        """ValueError is raised when the remote is not found."""
        mock_versions_fetcher.get_remote_info.return_value = None
        request = BuildRequest(
            vehicle_id="some-vehicle",
            board_id="some-board",
            version_id="some-version",
            selected_features=[],
        )

        with pytest.raises(ValueError, match="not whitelisted"):
            service.create_build(request)

    def test_create_build_raises_value_error_when_board_not_in_version(
        self,
        service,
        mock_ap_src_metadata_fetcher,
    ):
        """ValueError is raised when the board is not available for the version."""
        mock_ap_src_metadata_fetcher.get_boards.return_value = ["CubeOrange"]
        request = BuildRequest(
            vehicle_id="copter",
            board_id="some-nonexistent-board",
            version_id="copter-4.5.0-stable",
            selected_features=[],
        )

        with pytest.raises(ValueError, match="Invalid board for this version"):
            service.create_build(request)

    def test_create_build_maps_feature_labels_to_defines(
        self,
        service,
        mock_ap_src_metadata_fetcher,
        mock_build_manager,
    ):
        """Selected feature labels are translated to defines before build submission."""
        opt = Mock()
        opt.label = "HAL_LOGGING_ENABLED"
        opt.define = "HAL_LOGGING_ENABLED_DEFINE"
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="copter-4.5.0-stable",
            selected_features=["HAL_LOGGING_ENABLED"],
        )

        service.create_build(request)

        submitted: bm.BuildInfo = mock_build_manager.submit_build.call_args[1]["build_info"]
        assert "HAL_LOGGING_ENABLED_DEFINE" in submitted.selected_features

    def test_create_build_ignores_unknown_feature_labels(
        self,
        service,
        mock_ap_src_metadata_fetcher,
        mock_build_manager,
    ):
        """Unknown feature labels are silently skipped (not added to defines set)."""
        opt = Mock()
        opt.label = "HAL_LOGGING_ENABLED"
        opt.define = "HAL_LOGGING_ENABLED_DEFINE"
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="copter-4.5.0-stable",
            selected_features=["COMPLETELY_UNKNOWN_FEATURE"],
        )

        service.create_build(request)

        submitted: bm.BuildInfo = mock_build_manager.submit_build.call_args[1]["build_info"]
        assert len(submitted.selected_features) == 0

    def test_create_build_no_features_submits_empty_set(
        self,
        service,
        mock_build_manager,
    ):
        """When selected_features is empty, build is submitted with an empty set."""
        request = BuildRequest(
            vehicle_id="copter",
            board_id="MatekH743",
            version_id="copter-4.5.0-stable",
            selected_features=[],
        )

        service.create_build(request)

        submitted: bm.BuildInfo = mock_build_manager.submit_build.call_args[1]["build_info"]
        assert len(submitted.selected_features) == 0

    # Tests for list_builds

    def test_list_builds_returns_all_when_no_filters(
        self,
        service,
        mock_build_manager,
    ):
        """Returns all builds when no filters are applied."""
        self.setup_builds(
            mock_build_manager,
            [
                make_build_info(vehicle_id="copter", board="MatekH743"),
                make_build_info(vehicle_id="plane", board="CubeOrange"),
            ],
        )

        result = service.list_builds()

        assert len(result) == 2

    def test_list_builds_returns_empty_when_no_builds(
        self, service, mock_build_manager
    ):
        """Returns an empty list when there are no builds."""
        mock_build_manager.get_all_build_ids.return_value = []

        result = service.list_builds()

        assert result == []

    def test_list_builds_vehicle_id_filter_keeps_matching(
        self,
        service,
        mock_build_manager,
    ):
        """vehicle_id filter returns only builds for that vehicle."""
        self.setup_builds(
            mock_build_manager,
            [
                make_build_info(vehicle_id="copter"),
                make_build_info(vehicle_id="plane"),
                make_build_info(vehicle_id="copter"),
            ],
        )

        result = service.list_builds(vehicle_id="copter")

        assert len(result) == 2
        assert all(b.vehicle.id == "copter" for b in result)

    def test_list_builds_board_id_filter_keeps_matching(
        self,
        service,
        mock_build_manager,
    ):
        """board_id filter returns only builds for that board."""
        self.setup_builds(
            mock_build_manager,
            [
                make_build_info(board="MatekH743"),
                make_build_info(board="CubeOrange"),
                make_build_info(board="MatekH743"),
            ],
        )

        result = service.list_builds(board_id="MatekH743")

        assert len(result) == 2
        assert all(b.board.id == "MatekH743" for b in result)

    def test_list_builds_state_filter_keeps_matching(
        self,
        service,
        mock_build_manager,
    ):
        """state filter returns only builds in that state."""
        self.setup_builds(
            mock_build_manager,
            [
                make_build_info(state=bm.BuildState.PENDING),
                make_build_info(state=bm.BuildState.SUCCESS),
                make_build_info(state=bm.BuildState.PENDING),
            ],
        )

        result = service.list_builds(state="PENDING")

        assert len(result) == 2
        assert all(b.progress.state == "PENDING" for b in result)

    def test_list_builds_state_filter_excludes_non_matching(
        self,
        service,
        mock_build_manager,
    ):
        """state filter excludes builds not in that state."""
        self.setup_builds(
            mock_build_manager,
            [
                make_build_info(state=bm.BuildState.FAILURE),
                make_build_info(state=bm.BuildState.RUNNING),
            ],
        )

        result = service.list_builds(state="SUCCESS")

        assert result == []

    def test_list_builds_pagination_limit(
        self,
        service,
        mock_build_manager,
    ):
        """limit restricts the number of results returned."""
        self.setup_builds(
            mock_build_manager,
            [make_build_info() for _ in range(5)],
        )

        result = service.list_builds(limit=3)

        assert len(result) == 3

    def test_list_builds_pagination_offset(
        self,
        service,
        mock_build_manager,
    ):
        """offset skips the given number of results."""
        self.setup_builds(
            mock_build_manager,
            [make_build_info() for _ in range(5)],
        )

        result_all = service.list_builds(limit=5, offset=0)
        result_offset = service.list_builds(limit=5, offset=3)

        assert len(result_offset) == 2
        assert result_offset[0].build_id == result_all[3].build_id

    def test_list_builds_sorted_newest_first(
        self,
        service,
        mock_build_manager,
    ):
        """Builds are returned sorted by creation time, newest first."""
        now = time.time()
        old = make_build_info()
        old.time_created = now - 1000
        new = make_build_info()
        new.time_created = now

        ids = ["build-old", "build-new"]
        mock_build_manager.get_all_build_ids.return_value = ids
        mock_build_manager.get_build_info.side_effect = lambda bid: (
            old if bid == "build-old" else new
        )

        result = service.list_builds()

        assert result[0].time_created >= result[1].time_created

    def test_list_builds_skips_missing_build_info(
        self, service, mock_build_manager
    ):
        """Builds whose info cannot be retrieved are silently skipped."""
        mock_build_manager.get_all_build_ids.return_value = ["b1", "b2"]
        mock_build_manager.get_build_info.return_value = None

        result = service.list_builds()

        assert result == []

    # Tests for get_build

    def test_get_build_returns_build_out_when_found(
        self,
        service,
        mock_build_manager,
    ):
        """Returns a BuildOut when the build exists."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info()

        result = service.get_build("build-abc123")

        assert result is not None
        assert result.build_id == "build-abc123"

    def test_get_build_returns_none_when_not_found(
        self, service, mock_build_manager
    ):
        """Returns None when the build does not exist."""
        mock_build_manager.build_exists.return_value = False

        result = service.get_build("nonexistent-build")

        assert result is None

    def test_get_build_returns_none_when_info_unavailable(
        self, service, mock_build_manager
    ):
        """Returns None when build_exists is True but get_build_info returns None."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = None

        result = service.get_build("build-abc123")

        assert result is None

    def test_get_build_checks_existence_with_correct_id(
        self, service, mock_build_manager
    ):
        """build_exists is called with the provided build_id."""
        mock_build_manager.build_exists.return_value = False

        service.get_build("specific-build-id")

        mock_build_manager.build_exists.assert_called_once_with("specific-build-id")

    def test_get_build_output_has_correct_vehicle_and_board(
        self,
        service,
        mock_build_manager,
        mock_vehicles_manager,
    ):
        """The returned BuildOut contains correct vehicle and board information."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            vehicle_id="plane", board="CubeOrange"
        )
        mock_vehicle = Mock()
        mock_vehicle.name = "Plane"
        mock_vehicles_manager.get_vehicle_by_id.return_value = mock_vehicle

        result = service.get_build("build-xyz")

        assert result.vehicle.id == "plane"
        assert result.board.id == "CubeOrange"

    def test_get_build_maps_feature_defines_to_labels(
        self,
        service,
        mock_build_manager,
        mock_ap_src_metadata_fetcher,
    ):
        """Feature defines in BuildInfo are mapped back to labels in the output."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            selected_features={"HAL_LOGGING_ENABLED_DEFINE"}
        )
        opt = Mock()
        opt.define = "HAL_LOGGING_ENABLED_DEFINE"
        opt.label = "HAL_LOGGING_ENABLED"
        mock_ap_src_metadata_fetcher.get_build_options_at_commit.return_value = [opt]

        result = service.get_build("build-abc123")

        assert "HAL_LOGGING_ENABLED" in result.selected_features

    def test_get_build_falls_back_to_define_when_label_not_found(
        self,
        service,
        mock_build_manager,
    ):
        """When a define has no matching label, the define itself is used as fallback."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            selected_features={"ORPHANED_DEFINE"}
        )

        result = service.get_build("build-abc123")

        assert "ORPHANED_DEFINE" in result.selected_features

    def test_get_build_no_selected_features_returns_empty_list(
        self,
        service,
        mock_build_manager,
    ):
        """When a build has no selected features, the output list is empty."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            selected_features=set()
        )

        result = service.get_build("build-abc123")

        assert result.selected_features == []

    # Tests for get_build_logs

    def test_get_build_logs_returns_none_when_build_not_found(
        self, service, mock_build_manager
    ):
        """Returns None when the build does not exist."""
        mock_build_manager.build_exists.return_value = False

        result = service.get_build_logs("nonexistent-build")

        assert result is None

    def test_get_build_logs_returns_none_when_log_file_missing(
        self, service, mock_build_manager
    ):
        """Returns None when the log file does not exist on disk."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_log_path.return_value = "/nonexistent/path/build.log"

        result = service.get_build_logs("build-abc123")

        assert result is None

    def test_get_build_logs_returns_full_content_when_tail_is_none(
        self, service, mock_build_manager, tmp_path
    ):
        """Returns the full log content when tail is None."""
        log_file = tmp_path / "build.log"
        log_content = "line1\nline2\nline3\n"
        log_file.write_text(log_content)
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_log_path.return_value = str(log_file)

        result = service.get_build_logs("build-abc123", tail=None)

        assert result == log_content

    def test_get_build_logs_returns_last_n_lines_when_tail_given(
        self, service, mock_build_manager, tmp_path
    ):
        """Returns only the last N lines when tail is specified."""
        log_file = tmp_path / "build.log"
        log_file.write_text("line1\nline2\nline3\nline4\nline5\n")
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_log_path.return_value = str(log_file)

        result = service.get_build_logs("build-abc123", tail=2)

        assert result == "line4\nline5\n"

    def test_get_build_logs_checks_existence_with_correct_build_id(
        self, service, mock_build_manager
    ):
        """build_exists is called with the provided build_id."""
        mock_build_manager.build_exists.return_value = False

        service.get_build_logs("target-build-id")

        mock_build_manager.build_exists.assert_called_once_with("target-build-id")

    def test_get_build_logs_retrieves_path_with_correct_build_id(
        self, service, mock_build_manager, tmp_path
    ):
        """get_build_log_path is called with the correct build_id."""
        log_file = tmp_path / "build.log"
        log_file.write_text("")
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_log_path.return_value = str(log_file)

        service.get_build_logs("specific-build-id")

        mock_build_manager.get_build_log_path.assert_called_once_with("specific-build-id")

    # Tests for get_artifact_path

    def test_get_artifact_path_returns_none_when_build_not_found(
        self, service, mock_build_manager
    ):
        """Returns None when the build does not exist."""
        mock_build_manager.build_exists.return_value = False

        result = service.get_artifact_path("nonexistent-build")

        assert result is None

    def test_get_artifact_path_returns_none_when_build_info_unavailable(
        self, service, mock_build_manager
    ):
        """Returns None when build exists but its info cannot be retrieved."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = None

        result = service.get_artifact_path("build-abc123")

        assert result is None

    def test_get_artifact_path_returns_none_when_build_pending(
        self, service, mock_build_manager
    ):
        """Returns None when the build is in PENDING state."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            state=bm.BuildState.PENDING
        )

        result = service.get_artifact_path("build-abc123")

        assert result is None

    def test_get_artifact_path_returns_none_when_build_running(
        self, service, mock_build_manager
    ):
        """Returns None when the build is still RUNNING."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            state=bm.BuildState.RUNNING
        )

        result = service.get_artifact_path("build-abc123")

        assert result is None

    def test_get_artifact_path_returns_path_when_artifact_exists(
        self, service, mock_build_manager, tmp_path
    ):
        """Returns the artifact path when the build succeeded and file exists."""
        artifact = tmp_path / "artifact.tar.gz"
        artifact.write_bytes(b"firmware")
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            state=bm.BuildState.SUCCESS
        )
        mock_build_manager.get_build_archive_path.return_value = str(artifact)

        result = service.get_artifact_path("build-abc123")

        assert result == str(artifact)

    def test_get_artifact_path_returns_none_when_artifact_file_missing(
        self, service, mock_build_manager
    ):
        """Returns None when the build succeeded but the artifact file is absent."""
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            state=bm.BuildState.SUCCESS
        )
        mock_build_manager.get_build_archive_path.return_value = "/does/not/exist.tar.gz"

        result = service.get_artifact_path("build-abc123")

        assert result is None

    def test_get_artifact_path_available_for_failed_build_if_file_exists(
        self, service, mock_build_manager, tmp_path
    ):
        """Artifact path is returned for FAILURE state if the file happens to exist."""
        artifact = tmp_path / "artifact.tar.gz"
        artifact.write_bytes(b"partial firmware")
        mock_build_manager.build_exists.return_value = True
        mock_build_manager.get_build_info.return_value = make_build_info(
            state=bm.BuildState.FAILURE
        )
        mock_build_manager.get_build_archive_path.return_value = str(artifact)

        result = service.get_artifact_path("build-abc123")

        assert result == str(artifact)

    def test_get_artifact_path_uses_correct_build_id(
        self, service, mock_build_manager
    ):
        """build_exists is called with the correct build_id."""
        mock_build_manager.build_exists.return_value = False

        service.get_artifact_path("my-target-build")

        mock_build_manager.build_exists.assert_called_once_with("my-target-build")
