import logging
import re
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

from packaging.version import InvalidVersion, Version

from .models import BoardArtifact, ReleaseRecord

FIRMWARE_SERVER_BASE = "https://firmware.ardupilot.org"

# CBS vehicle id -> firmware.ardupilot.org top-level directory.
FIRMWARE_SERVER_DIR_BY_VEHICLE_ID = {
    "copter": "Copter",
    "plane": "Plane",
    "rover": "Rover",
    "sub": "Sub",
    "heli": "Copter",
    "blimp": "Blimp",
    "tracker": "AntennaTracker",
    "ap-periph": "AP_Periph",
}


def firmware_server_dir(vehicle_id: str) -> str:
    try:
        return FIRMWARE_SERVER_DIR_BY_VEHICLE_ID[vehicle_id]
    except KeyError as exc:
        raise ValueError(f"Unknown vehicle id: {vehicle_id}") from exc


def latest_features_txt_url(vehicle_id: str, board_id: str) -> str:
    """Hardcoded firmware-server latest features.txt URL for tag builds."""
    board_subdir = board_id + ("-heli" if vehicle_id == "heli" else "")
    return (
        f"{FIRMWARE_SERVER_BASE}/"
        f"{firmware_server_dir(vehicle_id)}/latest/"
        f"{board_subdir}/features.txt"
    )


# Minimum version for a vehicle to expose from manifest entries.
MIN_VERSION_BY_VEHICLE_ID = {
    "copter": "4.3",
    "plane": "4.3",
    "rover": "4.3",
    "sub": "4.3",
    "tracker": "4.3",
    "blimp": "4.3",
    "heli": "4.3",
    "ap-periph": "1.8.1",
}


def vehicle_id_for_manifest_entry(entry: dict) -> Optional[str]:
    match entry.get("vehicletype", ""):
        case "Copter":
            return "heli" if entry.get("mav-type") == "HELICOPTER" else "copter"
        case "Plane":
            return "plane"
        case "Rover":
            return "rover"
        case "Sub":
            return "sub"
        case "Blimp":
            return "blimp"
        case "AntennaTracker":
            return "tracker"
        case "AP_Periph":
            return "ap-periph"
        case _:
            return None


def _should_skip_version(
    vehicle_id: str, release_type: str, manifest_version: str
) -> bool:
    if release_type == "latest":
        return False

    min_version = MIN_VERSION_BY_VEHICLE_ID.get(vehicle_id)
    if not min_version:
        return False

    try:
        return Version(manifest_version) < Version(min_version)
    except InvalidVersion:
        return True


def map_manifest_release_type(mav_firmware_version_type: str) -> Optional[str]:
    if not mav_firmware_version_type:
        return None
    if mav_firmware_version_type.startswith("STABLE-"):
        return "stable"
    if mav_firmware_version_type == "OFFICIAL":
        return "stable"
    if mav_firmware_version_type == "BETA":
        return "beta"
    if mav_firmware_version_type == "DEV":
        return "latest"
    return mav_firmware_version_type.lower()


def parse_artifacts_base_url(url: str) -> Optional[str]:
    match = re.match(
        r"(https://firmware\.ardupilot\.org/[^/]+/[^/]+)/",
        url or "",
    )
    if match:
        return match.group(1)
    return None


def manifest_platform_key(platform: str, vehicle_id: str) -> str:
    """Normalize manifest platform field to the board id used for lookups."""
    if vehicle_id == "heli" and platform.endswith("-heli"):
        return platform[:-5]
    return platform


def _artifact_name_from_url(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1]


def _versioned_release_path_segment(release_type: str, version_number: str) -> str:
    if version_number == "NA":
        return release_type
    return f"{release_type}-{version_number}"


def _artifact_url_specificity(url: str, release_type: str, version_number: str) -> int:
    """Prefer versioned firmware-server paths over generic release aliases."""
    segment = _versioned_release_path_segment(release_type, version_number)
    if f"/{segment}/" in url:
        return 2
    if f"/{release_type}/" in url:
        return 1
    return 0


def _dedupe_board_artifacts(
    artifacts: list[BoardArtifact],
    release_type: str,
    version_number: str,
) -> list[BoardArtifact]:
    """Manifest entries may alias the same file under versioned and generic URLs."""
    by_name: dict[str, BoardArtifact] = {}
    for artifact in artifacts:
        existing = by_name.get(artifact.name)
        if existing is None or _artifact_url_specificity(
            artifact.url, release_type, version_number
        ) > _artifact_url_specificity(existing.url, release_type, version_number):
            by_name[artifact.name] = artifact
    return list(by_name.values())


def _release_fields_from_entry(
    entry: dict,
) -> Optional[tuple[str, str, str, str]]:
    vehicle_id = vehicle_id_for_manifest_entry(entry)
    if vehicle_id is None:
        return None

    release_type = map_manifest_release_type(
        entry.get("mav-firmware-version-type", "")
    )
    manifest_version = entry.get("mav-firmware-version")
    if not release_type or not manifest_version:
        return None

    if _should_skip_version(vehicle_id, release_type, manifest_version):
        return None

    base_url = parse_artifacts_base_url(entry.get("url", ""))
    if not base_url:
        return None

    git_sha = entry.get("git-sha")
    if not git_sha:
        return None

    version_number = "NA" if release_type == "latest" else manifest_version
    return vehicle_id, release_type, version_number, git_sha


def _record_release_meta(
    release_meta: dict[tuple, dict],
    vehicle_id: str,
    release_type: str,
    version_number: str,
    git_sha: str,
    logger: logging.Logger,
) -> None:
    key = (vehicle_id, release_type, version_number)
    if key not in release_meta:
        release_meta[key] = {
            "vehicle_id": vehicle_id,
            "release_type": release_type,
            "version_number": version_number,
            "git_sha": git_sha,
        }
        return

    if release_meta[key]["git_sha"] != git_sha:
        logger.debug(
            "Conflicting git-sha for %s: keeping %s, ignoring %s",
            key,
            release_meta[key]["git_sha"][:8],
            git_sha[:8],
        )


def _record_board_artifact(
    artifacts_by_release: dict[tuple[str, str, str], dict[str, list[BoardArtifact]]],
    entry: dict,
    vehicle_id: str,
    release_type: str,
    version_number: str,
) -> None:
    platform = entry.get("platform")
    artifact_url = entry.get("url", "")
    if not platform or not artifact_url:
        return

    platform = manifest_platform_key(platform, vehicle_id)
    key = (vehicle_id, release_type, version_number)
    artifacts_by_release[key][platform].append(
        BoardArtifact(
            name=_artifact_name_from_url(artifact_url),
            url=artifact_url,
            format=entry.get("format", ""),
            size=entry.get("image_size"),
        )
    )


def _releases_from_meta(
    release_meta: dict[tuple, dict],
) -> dict[str, list[ReleaseRecord]]:
    releases_by_vehicle: dict[str, list[ReleaseRecord]] = defaultdict(list)
    for meta in release_meta.values():
        releases_by_vehicle[meta["vehicle_id"]].append(
            ReleaseRecord(
                vehicle_id=meta["vehicle_id"],
                release_type=meta["release_type"],
                version_number=meta["version_number"],
                commit_reference=meta["git_sha"],
            )
        )

    for vehicle_id in releases_by_vehicle:
        releases_by_vehicle[vehicle_id].sort(
            key=lambda r: (
                0 if r.release_type == "latest" else 1,
                r.release_type,
                _version_sort_key(r.version_number),
            )
        )

    return dict(releases_by_vehicle)


class ManifestIndex:
    """In-memory index built from a parsed manifest document."""

    def __init__(
        self,
        releases_by_vehicle: dict[str, list[ReleaseRecord]],
        artifacts_by_release: dict[
            tuple[str, str, str], dict[str, list[BoardArtifact]]
        ],
    ):
        self.releases_by_vehicle = releases_by_vehicle
        self.artifacts_by_release = artifacts_by_release

    @classmethod
    def build(cls, manifest: dict) -> "ManifestIndex":
        logger = logging.getLogger(__name__)
        release_meta: dict[tuple, dict] = {}
        artifacts_by_release: dict[
            tuple[str, str, str], dict[str, list[BoardArtifact]]
        ] = defaultdict(lambda: defaultdict(list))

        for entry in manifest.get("firmware") or []:
            fields = _release_fields_from_entry(entry)
            if fields is None:
                continue
            vehicle_id, release_type, version_number, git_sha = fields
            _record_release_meta(
                release_meta,
                vehicle_id,
                release_type,
                version_number,
                git_sha,
                logger,
            )
            _record_board_artifact(
                artifacts_by_release,
                entry,
                vehicle_id,
                release_type,
                version_number,
            )

        return cls(
            _releases_from_meta(release_meta),
            {
                release_key: dict(platforms)
                for release_key, platforms in artifacts_by_release.items()
            },
        )

    def get_releases(self, vehicle_id: str) -> list[ReleaseRecord]:
        return list(self.releases_by_vehicle.get(vehicle_id, []))

    def get_board_artifacts(
        self,
        vehicle_id: str,
        release_type: str,
        version_number: str,
        board_id: str,
    ) -> list[BoardArtifact]:
        key = (vehicle_id, release_type, version_number)
        artifacts = list(self.artifacts_by_release.get(key, {}).get(board_id, []))
        return _dedupe_board_artifacts(artifacts, release_type, version_number)

    def get_features_txt_url(
        self,
        vehicle_id: str,
        release_type: str,
        version_number: str,
        board_id: str,
    ) -> Optional[str]:
        artifacts = self.get_board_artifacts(
            vehicle_id, release_type, version_number, board_id
        )
        if not artifacts:
            return None
        return artifacts[0].url.rsplit("/", 1)[0] + "/features.txt"


def _version_sort_key(version_number: str) -> tuple:
    if version_number == "NA":
        return (0,)
    try:
        parsed = Version(version_number)
        return (1, parsed.major, parsed.minor, parsed.micro)
    except InvalidVersion:
        return (2, version_number)
