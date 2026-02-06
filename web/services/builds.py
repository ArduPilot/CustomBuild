"""
Builds service for handling build-related business logic.
"""
import logging
import os
from fastapi import Request
from typing import List, Optional

from schemas import (
    BuildRequest,
    BuildSubmitResponse,
    BuildOut,
    BuildProgress,
    RemoteInfo,
    BuildVersionInfo,
)
from schemas.vehicles import VehicleBase, BoardBase

# Import external modules
# pylint: disable=wrong-import-position
import build_manager  # noqa: E402

logger = logging.getLogger(__name__)


class BuildsService:
    """Service for managing firmware builds."""

    def __init__(
        self,
        build_manager=None,
        versions_fetcher=None,
        ap_src_metadata_fetcher=None,
        repo=None,
        vehicles_manager=None
    ):
        self.manager = build_manager
        self.versions_fetcher = versions_fetcher
        self.ap_src_metadata_fetcher = ap_src_metadata_fetcher
        self.repo = repo
        self.vehicles_manager = vehicles_manager

    def create_build(
        self,
        build_request: BuildRequest,
        client_ip: str
    ) -> BuildSubmitResponse:
        """
        Create a new build request.

        Args:
            build_request: Build configuration
            client_ip: Client IP address for rate limiting

        Returns:
            Simple response with build_id and URL

        Raises:
            ValueError: If validation fails
        """
        # Validate version_id
        if not build_request.version_id:
            raise ValueError("version_id is required")

        # Validate vehicle
        vehicle_id = build_request.vehicle_id
        if not vehicle_id:
            raise ValueError("vehicle_id is required")

        # Get version info using version_id
        version_info = self.versions_fetcher.get_version_info(
            vehicle_id=vehicle_id,
            version_id=build_request.version_id
        )
        if version_info is None:
            raise ValueError("Invalid version_id for vehicle")

        remote_name = version_info.remote_info.name
        commit_ref = version_info.commit_ref

        # Validate remote
        remote_info = self.versions_fetcher.get_remote_info(remote_name)
        if remote_info is None:
            raise ValueError(f"Remote {remote_name} is not whitelisted")

        # Validate board
        board_name = build_request.board_id
        if not board_name:
            raise ValueError("board_id is required")

        # Check board exists at this version
        with self.repo.get_checkout_lock():
            boards_at_commit = self.ap_src_metadata_fetcher.get_boards(
                remote=remote_name,
                commit_ref=commit_ref,
                vehicle_id=vehicle_id,
            )

        if board_name not in boards_at_commit:
            raise ValueError("Invalid board for this version")

        # Get git hash
        git_hash = self.repo.commit_id_for_remote_ref(
            remote=remote_name,
            commit_ref=commit_ref
        )

        # Map feature labels (IDs from API) to defines
        # (required by build manager)
        selected_feature_defines = set()
        if build_request.selected_features:
            # Get build options to map labels to defines
            with self.repo.get_checkout_lock():
                options = (
                    self.ap_src_metadata_fetcher
                    .get_build_options_at_commit(
                        remote=remote_name,
                        commit_ref=commit_ref
                    )
                )

            # Create label to define mapping
            label_to_define = {
                option.label: option.define for option in options
            }

            # Map each selected feature label to its define
            for feature_label in build_request.selected_features:
                if feature_label in label_to_define:
                    selected_feature_defines.add(
                        label_to_define[feature_label]
                    )
                else:
                    logger.warning(
                        f"Feature label '{feature_label}' not found in "
                        f"build options for {vehicle_id} {remote_name} "
                        f"{commit_ref}"
                    )

        # Create build info
        build_info = build_manager.BuildInfo(
            vehicle_id=vehicle_id,
            version_id=build_request.version_id,
            remote_info=remote_info,
            git_hash=git_hash,
            board=board_name,
            selected_features=selected_feature_defines
        )

        # Submit build
        build_id = self.manager.submit_build(
            build_info=build_info,
            client_ip=client_ip,
        )

        # Return simple submission response
        return BuildSubmitResponse(
            build_id=build_id,
            url=f"/api/v1/builds/{build_id}",
            status="submitted"
        )

    def list_builds(
        self,
        vehicle_id: Optional[str] = None,
        board_id: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[BuildOut]:
        """
        Get list of builds with optional filters.

        Args:
            vehicle_id: Filter by vehicle
            board_id: Filter by board
            state: Filter by build state
            limit: Maximum results
            offset: Results to skip

        Returns:
            List of builds
        """
        all_build_ids = self.manager.get_all_build_ids()
        all_builds = []

        for build_id in all_build_ids:
            build_info = self.manager.get_build_info(build_id)
            if build_info is None:
                continue

            # Apply filters
            if (vehicle_id and
                    build_info.vehicle_id.lower() != vehicle_id.lower()):
                continue
            if board_id and build_info.board != board_id:
                continue
            if state and build_info.progress.state.name != state:
                continue

            all_builds.append(
                self._build_info_to_output(build_id, build_info)
            )

        # Sort by creation time (newest first)
        all_builds.sort(key=lambda x: x.time_created, reverse=True)

        # Apply pagination
        return all_builds[offset:offset + limit]

    def get_build(self, build_id: str) -> Optional[BuildOut]:
        """
        Get details of a specific build.

        Args:
            build_id: The unique build identifier

        Returns:
            Build details or None if not found
        """
        if not self.manager.build_exists(build_id):
            return None

        build_info = self.manager.get_build_info(build_id)
        if build_info is None:
            return None

        return self._build_info_to_output(build_id, build_info)

    def get_build_logs(
        self,
        build_id: str,
        tail: Optional[int] = None
    ) -> Optional[str]:
        """
        Get build logs for a specific build.

        Args:
            build_id: The unique build identifier
            tail: Optional number of last lines to return

        Returns:
            Build logs as text or None if not found/available
        """
        if not self.manager.build_exists(build_id):
            return None

        log_path = self.manager.get_build_log_path(build_id)
        if not os.path.exists(log_path):
            return None

        try:
            with open(log_path, 'r') as f:
                if tail:
                    # Read last N lines
                    lines = f.readlines()
                    return ''.join(lines[-tail:])
                else:
                    return f.read()
        except Exception as e:
            logger.error(f"Error reading log file for build {build_id}: {e}")
            return None

    def get_artifact_path(self, build_id: str) -> Optional[str]:
        """
        Get the path to the build artifact.

        Args:
            build_id: The unique build identifier

        Returns:
            Path to artifact or None if not available
        """
        if not self.manager.build_exists(build_id):
            return None

        build_info = self.manager.get_build_info(build_id)
        if build_info is None:
            return None

        # Only return artifact if build was successful
        if build_info.progress.state.name != "SUCCESS":
            return None

        artifact_path = self.manager.get_build_archive_path(build_id)
        if os.path.exists(artifact_path):
            return artifact_path

        return None

    def _build_info_to_output(
        self,
        build_id: str,
        build_info
    ) -> BuildOut:
        """
        Convert BuildInfo object to BuildOut schema.

        Args:
            build_id: The build identifier
            build_info: BuildInfo object from build_manager

        Returns:
            BuildOut schema object
        """
        # Convert build_manager.BuildProgress to schema BuildProgress
        progress = BuildProgress(
            percent=build_info.progress.percent,
            state=build_info.progress.state.name
        )

        # Convert RemoteInfo
        remote_info = RemoteInfo(
            name=build_info.remote_info.name,
            url=build_info.remote_info.url
        )

        # Map feature defines back to labels for API response
        selected_feature_labels = []
        if build_info.selected_features:
            try:
                # Get build options to map defines back to labels
                with self.repo.get_checkout_lock():
                    options = (
                        self.ap_src_metadata_fetcher
                        .get_build_options_at_commit(
                            remote=build_info.remote_info.name,
                            commit_ref=build_info.git_hash
                        )
                    )

                # Create define to label mapping
                define_to_label = {
                    option.define: option.label for option in options
                }

                # Map each selected feature define to its label
                for feature_define in build_info.selected_features:
                    if feature_define in define_to_label:
                        selected_feature_labels.append(
                            define_to_label[feature_define]
                        )
                    else:
                        # Fallback: use define if label not found
                        logger.warning(
                            f"Feature define '{feature_define}' not "
                            f"found in build options for build "
                            f"{build_id}"
                        )
                        selected_feature_labels.append(feature_define)
            except Exception as e:
                logger.error(
                    f"Error mapping feature defines to labels for "
                    f"build {build_id}: {e}"
                )
                # Fallback: use defines as-is
                selected_feature_labels = list(
                    build_info.selected_features
                )

        vehicle = self.vehicles_manager.get_vehicle_by_id(
            build_info.vehicle_id
        )

        return BuildOut(
            build_id=build_id,
            vehicle=VehicleBase(
                id=build_info.vehicle_id,
                name=vehicle.name
            ),
            board=BoardBase(
                id=build_info.board,
                name=build_info.board  # Board name is same as board ID for now
            ),
            version=BuildVersionInfo(
                id=build_info.version_id,
                remote_info=remote_info,
                git_hash=build_info.git_hash
            ),
            selected_features=selected_feature_labels,
            progress=progress,
            time_created=build_info.time_created,
        )


def get_builds_service(request: Request) -> BuildsService:
    """
    Get BuildsService instance with dependencies from app state.

    Args:
        request: FastAPI Request object

    Returns:
        BuildsService instance initialized with app state dependencies
    """
    return BuildsService(
        build_manager=request.app.state.build_manager,
        versions_fetcher=request.app.state.versions_fetcher,
        ap_src_metadata_fetcher=request.app.state.ap_src_metadata_fetcher,
        repo=request.app.state.repo,
        vehicles_manager=request.app.state.vehicles_manager,
    )
