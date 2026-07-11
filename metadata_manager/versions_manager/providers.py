import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Optional

import jsonschema
import requests

from metadata_manager.vehicles_manager import DEFAULT_VEHICLES

from metadata_manager.firmware_server import ManifestJSON
from metadata_manager.firmware_server.models import ReleaseRecord

from .models import ForkRemoteSpec, RemoteInfo, VersionInfo

OFFICIAL_REMOTE_NAME = "ardupilot"
OFFICIAL_REMOTE_URL = "https://github.com/ardupilot/ardupilot.git"
FIRMWARE_SERVER_BASE = "https://firmware.ardupilot.org"

# CBS vehicle id -> firmware.ardupilot.org top-level directory.
_FIRMWARE_SERVER_DIR_BY_VEHICLE_ID = {
    "copter": "Copter",
    "plane": "Plane",
    "rover": "Rover",
    "sub": "Sub",
    "heli": "Copter",
    "blimp": "Blimp",
    "tracker": "AntennaTracker",
    "ap-periph": "AP_Periph",
}


def _firmware_server_dir(vehicle_id: str) -> str:
    try:
        return _FIRMWARE_SERVER_DIR_BY_VEHICLE_ID[vehicle_id]
    except KeyError as exc:
        raise ValueError(f"Unknown vehicle id: {vehicle_id}") from exc


def _vehicle_id_for_tag_segment(segment: str) -> Optional[str]:
    for vehicle in DEFAULT_VEHICLES:
        if vehicle.name == segment or vehicle.id == segment:
            return vehicle.id
    return None


DEFAULT_WHITELISTED_FORK_REMOTES = [
    ForkRemoteSpec(owner="tridge", repo="ardupilot"),
    ForkRemoteSpec(owner="peterbarker", repo="ardupilot"),
    ForkRemoteSpec(owner="rmackay9", repo="rmackay9-ardupilot"),
    ForkRemoteSpec(owner="shiv-tyagi", repo="ardupilot"),
    ForkRemoteSpec(owner="andyp1per", repo="ardupilot"),
]


class VersionsProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def get_versions(self, vehicle_id: str) -> list[VersionInfo]:
        ...

    @abstractmethod
    def get_remotes(self) -> list[RemoteInfo]:
        ...

    def refresh(self) -> None:
        """Optional hook to refresh provider data."""

    @property
    def is_available(self) -> bool:
        return True


class ManifestJsonVersionsProvider(VersionsProvider):
    name = "official-ardupilot"

    def __init__(self, manifest_json: ManifestJSON):
        self._manifest_json = manifest_json
        self._remote = RemoteInfo(OFFICIAL_REMOTE_NAME, OFFICIAL_REMOTE_URL)

    @property
    def is_available(self) -> bool:
        return self._manifest_json.is_available

    def refresh(self) -> None:
        self._manifest_json.refresh()

    def get_remotes(self) -> list[RemoteInfo]:
        if not self.is_available:
            return []
        return [self._remote]

    def get_versions(self, vehicle_id: str) -> list[VersionInfo]:
        if not self.is_available:
            return []

        return [
            VersionInfo.from_release_record(self._remote, release)
            for release in self._manifest_json.get_releases(vehicle_id)
        ]


class WhitelistedForkTagVersionsProvider(VersionsProvider):
    """
    Discover custom-build tags from whitelisted GitHub forks.

    Only tags with the ``custom-build/`` prefix are included. Vehicle-specific
    tag segments may use a vehicle name (e.g. ``Copter``) or id (e.g. ``copter``).

    Tag format examples:
    - ``custom-build/my-feature`` — listed for all vehicles
    - ``custom-build/Copter/my-feature`` — listed for Copter only
    - ``custom-build/copter/my-feature`` — listed for Copter only
    """

    name = "whitelisted-fork-tags"

    def __init__(
        self,
        fork_remotes: Optional[list[ForkRemoteSpec]] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self._fork_remotes = fork_remotes or DEFAULT_WHITELISTED_FORK_REMOTES
        self._vehicle_ids = [v.id for v in DEFAULT_VEHICLES]
        self._versions_by_remote_vehicle: dict[str, dict[str, list[ReleaseRecord]]] = {}
        self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def get_remotes(self) -> list[RemoteInfo]:
        if not self.is_available:
            return []
        fork_by_owner = {spec.owner: spec for spec in self._fork_remotes}
        return [
            RemoteInfo(name=remote_name, url=fork_by_owner[remote_name].url)
            for remote_name in self._versions_by_remote_vehicle
            if remote_name != OFFICIAL_REMOTE_NAME and remote_name in fork_by_owner
        ]

    def refresh(self) -> None:
        versions_map = {
            spec.owner: {vehicle_id: [] for vehicle_id in self._vehicle_ids}
            for spec in self._fork_remotes
        }

        for spec in self._fork_remotes:
            if spec.owner == OFFICIAL_REMOTE_NAME:
                continue
            try:
                tag_objs = self._fetch_tags_from_github(spec.github_repo)
            except Exception as exc:
                self.logger.warning(
                    "Skipping remote %s (%s): %s",
                    spec.owner,
                    spec.github_repo,
                    exc,
                )
                continue

            for tag_info in tag_objs:
                ref = tag_info["ref"].replace("refs/tags/", "")
                parts = ref.split("/", 3)
                if len(parts) <= 1 or parts[0] != "custom-build":
                    continue

                tag_vehicle_id = _vehicle_id_for_tag_segment(parts[1])
                if tag_vehicle_id is not None:
                    if len(parts) == 2:
                        continue
                    vehicles_for_tag = [tag_vehicle_id]
                else:
                    vehicles_for_tag = self._vehicle_ids

                for vid in vehicles_for_tag:
                    versions_map[spec.owner][vid].append(
                        ReleaseRecord(
                            vehicle_id=vid,
                            release_type="tag",
                            version_number=parts[-1],
                            commit_reference=tag_info["object"]["sha"],
                            ap_build_artifacts_url=(
                                f"{FIRMWARE_SERVER_BASE}/"
                                f"{_firmware_server_dir(vid)}/latest"
                            ),
                        )
                    )

        self._versions_by_remote_vehicle = versions_map
        self._available = True

    def get_versions(self, vehicle_id: str) -> list[VersionInfo]:
        if not self.is_available:
            return []

        fork_by_owner = {spec.owner: spec for spec in self._fork_remotes}
        versions = []
        for remote_name, vehicles_map in self._versions_by_remote_vehicle.items():
            if remote_name == OFFICIAL_REMOTE_NAME:
                continue
            spec = fork_by_owner.get(remote_name)
            if spec is None:
                continue
            remote = RemoteInfo(name=spec.owner, url=spec.url)
            for release in vehicles_map.get(vehicle_id, []):
                versions.append(VersionInfo.from_release_record(remote, release))
        return versions

    def _fetch_tags_from_github(self, github_repo: str) -> list:
        url = f"https://api.github.com/repos/{github_repo}/git/refs/tags"
        headers = {
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github+json",
        }
        token = os.getenv("CBS_GITHUB_ACCESS_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.get(url=url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()


class RemotesJsonVersionsProvider(VersionsProvider):
    name = "remotes-json"

    def __init__(self, remotes_json_path: str, schema_path: str):
        self._remotes_json_path = remotes_json_path
        self._schema_path = schema_path
        self._lock = Lock()
        self._metadata: list = []

    @property
    def is_available(self) -> bool:
        return bool(self._metadata)

    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        path = Path(self._remotes_json_path)
        if not path.is_file():
            with self._lock:
                self._metadata = []
            return

        content = path.read_text(encoding="utf-8")
        if not content.strip():
            with self._lock:
                self._metadata = []
            return

        metadata = json.loads(content)
        schema = json.loads(Path(self._schema_path).read_text(encoding="utf-8"))
        jsonschema.validate(instance=metadata, schema=schema)

        with self._lock:
            self._metadata = metadata

    def get_remotes(self) -> list[RemoteInfo]:
        with self._lock:
            metadata = list(self._metadata)
        return [
            RemoteInfo(name=remote.get("name"), url=remote.get("url"))
            for remote in metadata
            if remote.get("name") and remote.get("url")
        ]

    def get_versions(self, vehicle_id: str) -> list[VersionInfo]:
        versions = []
        with self._lock:
            metadata = list(self._metadata)

        for remote in metadata:
            remote_info = RemoteInfo(
                name=remote.get("name"),
                url=remote.get("url"),
            )
            for remote_vehicle in remote.get("vehicles", []):
                if remote_vehicle.get("id") != vehicle_id:
                    continue
                for release in remote_vehicle.get("releases", []):
                    versions.append(
                        VersionInfo(
                            remote_info=remote_info,
                            commit_ref=release.get("commit_reference"),
                            release_type=release.get("release_type"),
                            version_number=release.get("version_number"),
                            ap_build_artifacts_url=release.get(
                                "ap_build_artifacts_url"
                            ),
                        )
                    )
        return versions


def build_default_providers(
    manifest_json: ManifestJSON,
    remotes_json_path: str,
    schema_path: str,
    fork_remotes: Optional[list[ForkRemoteSpec]] = None,
) -> list[VersionsProvider]:
    return [
        ManifestJsonVersionsProvider(manifest_json),
        WhitelistedForkTagVersionsProvider(fork_remotes=fork_remotes),
        RemotesJsonVersionsProvider(
            remotes_json_path=remotes_json_path,
            schema_path=schema_path,
        ),
    ]
