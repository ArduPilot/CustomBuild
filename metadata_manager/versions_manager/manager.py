import logging
from pathlib import Path

import ap_git
from utils import TaskRunner

from metadata_manager.versions_manager.models import RemoteInfo, VersionInfo
from metadata_manager.versions_manager.providers import (
    VersionsProvider,
    build_default_providers,
)
from metadata_manager.vehicles_manager import VehiclesManager as vehm

REMOTES_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "remotes.schema.json"


def _release_type_dedup_priority(release_type: str) -> int:
    """Lower value wins when multiple releases collide on a dedup key."""
    match release_type:
        case "stable":
            return 0
        case "beta":
            return 1
        case "latest":
            return 2
        case "tag":
            return 3
        case _:
            return 99


def _version_dedup_key(version: VersionInfo) -> str:
    """
    Collapse releases that share a real version number (e.g. stable+beta 4.7.0).

    Placeholder numbers like "NA" (latest/dev) keep identity by version_id so
    unrelated entries are not merged.
    """
    number = (version.version_number or "").strip()
    if number and number.upper() != "NA":
        return f"num:{number}"
    return f"id:{version.version_id}"


class VersionsManager:
    """
    Version manager merges version metadata from different pluggable providers.
    """

    __singleton = None

    def __init__(
        self,
        ap_repo: ap_git.GitRepo,
        remotes_json_path: str,
        manifest_json=None,
        providers: list[VersionsProvider] | None = None,
    ):
        if vehm.get_singleton() is None:
            raise RuntimeError("VehiclesManager should be initialised first")

        if VersionsManager.__singleton:
            raise RuntimeError("VersionsManager must be a singleton.")

        self.logger = logging.getLogger(__name__)
        if providers is None:
            if manifest_json is None:
                raise ValueError("manifest_json is required when providers is omitted")
            providers = build_default_providers(
                manifest_json=manifest_json,
                remotes_json_path=remotes_json_path,
                schema_path=str(REMOTES_SCHEMA_PATH),
            )
        self._providers = providers
        self.repo = ap_repo
        self._remotes_json_path = remotes_json_path
        self.__task__runner = TaskRunner(tasks=((self.refresh_all, 1200),))
        VersionsManager.__singleton = self

    def start(self) -> None:
        self.logger.info("Starting VersionsManager background refresh jobs.")
        self.__task__runner.start()

    def stop(self) -> None:
        self.logger.info("Stopping VersionsManager background refresh jobs.")
        self.__task__runner.stop()

    def refresh_all(self) -> None:
        for provider in self._providers:
            try:
                provider.refresh()
            except Exception as exc:
                self.logger.error(
                    "Provider %s refresh failed: %s", provider.name, exc
                )
        self._sync_remotes_with_ap_repo()

    def get_all_remotes_info(self) -> list[RemoteInfo]:
        remotes = {}
        for provider in self._providers:
            for remote in provider.get_remotes():
                remotes[remote.name] = remote
        return list(remotes.values())

    def get_remote_info(self, remote_name: str) -> RemoteInfo | None:
        return next(
            (remote for remote in self.get_all_remotes_info()
             if remote.name == remote_name),
            None,
        )

    def get_versions_for_vehicle(self, vehicle_id: str) -> list[VersionInfo]:
        if vehicle_id is None:
            raise ValueError("Vehicle ID is a required parameter.")

        vehicle = vehm.get_singleton().get_vehicle_by_id(vehicle_id)
        if vehicle is None:
            raise ValueError(f"Invalid vehicle ID '{vehicle_id}'.")

        by_key: dict[str, VersionInfo] = {}
        for provider in self._providers:
            for version in provider.get_versions(vehicle_id):
                key = _version_dedup_key(version)
                existing = by_key.get(key)
                if existing is None:
                    by_key[key] = version
                    continue
                if _release_type_dedup_priority(version.release_type) < (
                    _release_type_dedup_priority(existing.release_type)
                ):
                    by_key[key] = version
        return list(by_key.values())

    def is_version_listed(self, vehicle_id: str, version_id: str) -> bool:
        if vehicle_id is None:
            raise ValueError("vehicle_id is a required parameter.")
        if version_id is None:
            raise ValueError("version_id is a required parameter.")

        return version_id in [
            version.version_id
            for version in self.get_versions_for_vehicle(vehicle_id=vehicle_id)
        ]

    def get_version_info(self, vehicle_id: str, version_id: str) -> VersionInfo | None:
        return next(
            (
                version
                for version in self.get_versions_for_vehicle(vehicle_id=vehicle_id)
                if version.version_id == version_id
            ),
            None,
        )

    def _sync_remotes_with_ap_repo(self) -> None:
        remotes = tuple(
            (remote.name, remote.url)
            for remote in self.get_all_remotes_info()
        )
        if remotes:
            self.repo.remote_add_bulk(remotes=remotes, force=True)

    @staticmethod
    def get_singleton():
        return VersionsManager.__singleton
