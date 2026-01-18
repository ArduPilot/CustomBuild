"""
Vehicles service for handling vehicle-related business logic.
"""
import logging
from typing import List, Optional
from fastapi import Request

from schemas import (
    VehicleBase,
    RemoteInfo,
    VersionOut,
    BoardOut,
    FeatureOut,
    CategoryBase,
    FeatureDefault,
)


logger = logging.getLogger(__name__)


class VehiclesService:
    """Service for managing vehicles, versions, boards, and features."""

    def __init__(self, vehicle_manager=None,
                 versions_fetcher=None,
                 ap_src_metadata_fetcher=None,
                 repo=None):
        self.vehicles_manager = vehicle_manager
        self.versions_fetcher = versions_fetcher
        self.ap_src_metadata_fetcher = ap_src_metadata_fetcher
        self.repo = repo

    def get_all_vehicles(self) -> List[VehicleBase]:
        """Get list of all available vehicles."""
        logger.info('Fetching all vehicles')
        vehicles = self.vehicles_manager.get_all_vehicles()
        # Sort by name for consistent ordering
        sorted_vehicles = sorted(vehicles, key=lambda v: v.name)
        logger.info(f'Found vehicles: {[v.name for v in sorted_vehicles]}')
        return [
            VehicleBase(id=vehicle.id, name=vehicle.name)
            for vehicle in sorted_vehicles
        ]

    def get_vehicle(self, vehicle_id: str) -> Optional[VehicleBase]:
        """Get a specific vehicle by ID."""
        vehicle = self.vehicles_manager.get_vehicle_by_id(vehicle_id)
        if vehicle:
            return VehicleBase(id=vehicle.id, name=vehicle.name)
        return None

    def get_versions(
        self,
        vehicle_id: str,
        type_filter: Optional[str] = None
    ) -> List[VersionOut]:
        """Get all versions available for a specific vehicle."""
        versions = []

        for version_info in self.versions_fetcher.get_versions_for_vehicle(
            vehicle_id=vehicle_id
        ):
            # Apply type filter if provided
            if type_filter and version_info.release_type != type_filter:
                continue

            if version_info.release_type == "latest":
                title = f"Latest ({version_info.remote_info.name})"
            else:
                rel_type = version_info.release_type
                ver_num = version_info.version_number
                remote = version_info.remote_info.name
                title = f"{rel_type} {ver_num} ({remote})"

            versions.append(VersionOut(
                id=version_info.version_id,
                name=title,
                type=version_info.release_type,
                remote=RemoteInfo(
                    name=version_info.remote_info.name,
                    url=version_info.remote_info.url,
                ),
                commit_ref=version_info.commit_ref,
                vehicle_id=vehicle_id,
            ))

        # Sort by name
        return sorted(versions, key=lambda x: x.name)

    def get_version(
        self,
        vehicle_id: str,
        version_id: str
    ) -> Optional[VersionOut]:
        """Get details of a specific version for a vehicle."""
        versions = self.get_versions(vehicle_id)
        for version in versions:
            if version.id == version_id:
                return version
        return None

    def get_boards(
        self,
        vehicle_id: str,
        version_id: str
    ) -> List[BoardOut]:
        """Get all boards available for a specific vehicle version."""
        # Get version info
        version_info = self.versions_fetcher.get_version_info(
            vehicle_id=vehicle_id,
            version_id=version_id
        )
        if not version_info:
            return []

        logger.info(
            f'Board list requested for {vehicle_id} '
            f'{version_info.remote_info.name} {version_info.commit_ref}'
        )

        # Get boards list
        with self.repo.get_checkout_lock():
            boards = self.ap_src_metadata_fetcher.get_boards(
                remote=version_info.remote_info.name,
                commit_ref=version_info.commit_ref,
                vehicle_id=vehicle_id,
            )

        return [
            BoardOut(
                id=board,
                name=board,
                vehicle_id=vehicle_id,
                version_id=version_id
            )
            for board in boards
        ]

    def get_board(
        self,
        vehicle_id: str,
        version_id: str,
        board_id: str
    ) -> Optional[BoardOut]:
        """Get details of a specific board for a vehicle version."""
        boards = self.get_boards(vehicle_id, version_id)
        for board in boards:
            if board.id == board_id:
                return board
        return None

    def get_features(
        self,
        vehicle_id: str,
        version_id: str,
        board_id: str,
        category_id: Optional[str] = None
    ) -> List[FeatureOut]:
        """
        Get all features with defaults for a specific
        vehicle version/board.
        """
        # Get version info
        version_info = self.versions_fetcher.get_version_info(
            vehicle_id=vehicle_id,
            version_id=version_id
        )
        if not version_info:
            return []

        logger.info(
            f'Features requested for {vehicle_id} '
            f'{version_info.remote_info.name} {version_info.commit_ref}'
        )

        # Get build options from source
        with self.repo.get_checkout_lock():
            options = self.ap_src_metadata_fetcher.get_build_options_at_commit(
                remote=version_info.remote_info.name,
                commit_ref=version_info.commit_ref
            )

        # Try to fetch board-specific defaults from firmware-server
        board_defaults = None
        artifacts_dir = version_info.ap_build_artifacts_url
        if artifacts_dir is not None:
            board_defaults = (
                self.ap_src_metadata_fetcher.get_board_defaults_from_fw_server(
                    artifacts_url=artifacts_dir,
                    board_id=board_id,
                    vehicle_id=vehicle_id,
                )
            )

        # Build feature list
        features = []
        for option in options:
            # Apply category filter if provided
            if category_id and option.category != category_id:
                continue

            # Determine default state and source
            if board_defaults and option.define in board_defaults:
                # Override with firmware server data
                default_enabled = (board_defaults[option.define] != 0)
                default_source = 'firmware-server'
            else:
                # Use build-options-py fallback
                default_enabled = (option.default != 0)
                default_source = 'build-options-py'

            # Parse dependencies (comma-separated labels)
            dependencies = []
            if option.dependency:
                dependencies = [
                    label.strip()
                    for label in option.dependency.split(',')
                ]

            features.append(FeatureOut(
                id=option.label,
                name=option.label,
                category=CategoryBase(
                    id=option.category,
                    name=option.category,
                    description=None
                ),
                description=option.description,
                vehicle_id=vehicle_id,
                version_id=version_id,
                board_id=board_id,
                default=FeatureDefault(
                    enabled=default_enabled,
                    source=default_source
                ),
                dependencies=dependencies
            ))

        # Sort by name
        return sorted(features, key=lambda x: x.category.name)

    def get_feature(
        self,
        vehicle_id: str,
        version_id: str,
        board_id: str,
        feature_id: str
    ) -> Optional[FeatureOut]:
        """Get details of a specific feature for a vehicle version/board."""
        features = self.get_features(vehicle_id, version_id, board_id)
        for feature in features:
            if feature.id == feature_id:
                return feature
        return None


def get_vehicles_service(request: Request) -> VehiclesService:
    """
    Get VehiclesService instance with dependencies from app state.

    Args:
        request: FastAPI Request object

    Returns:
        VehiclesService instance initialized with app state dependencies
    """
    return VehiclesService(
        vehicle_manager=request.app.state.vehicles_manager,
        versions_fetcher=request.app.state.versions_fetcher,
        ap_src_metadata_fetcher=request.app.state.ap_src_metadata_fetcher,
        repo=request.app.state.repo,
    )
