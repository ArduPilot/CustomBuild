import logging
import re
from collections import defaultdict
from typing import Optional

from packaging.version import InvalidVersion, Version

from .models import ReleaseRecord

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


def _release_fields_from_entry(
    entry: dict,
) -> Optional[tuple[str, str, str, str, str]]:
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
    return vehicle_id, release_type, version_number, base_url, git_sha


def _record_release_meta(
    release_meta: dict[tuple, dict],
    vehicle_id: str,
    release_type: str,
    version_number: str,
    base_url: str,
    git_sha: str,
    logger: logging.Logger,
) -> None:
    key = (vehicle_id, release_type, version_number)
    if key not in release_meta:
        release_meta[key] = {
            "vehicle_id": vehicle_id,
            "release_type": release_type,
            "version_number": version_number,
            "ap_build_artifacts_url": base_url,
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
                ap_build_artifacts_url=meta["ap_build_artifacts_url"],
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

    def __init__(self, releases_by_vehicle: dict[str, list[ReleaseRecord]]):
        self.releases_by_vehicle = releases_by_vehicle

    @classmethod
    def build(cls, manifest: dict) -> "ManifestIndex":
        logger = logging.getLogger(__name__)
        release_meta: dict[tuple, dict] = {}

        for entry in manifest.get("firmware") or []:
            fields = _release_fields_from_entry(entry)
            if fields is None:
                continue
            vehicle_id, release_type, version_number, base_url, git_sha = fields
            _record_release_meta(
                release_meta,
                vehicle_id,
                release_type,
                version_number,
                base_url,
                git_sha,
                logger,
            )

        return cls(_releases_from_meta(release_meta))

    def get_releases(self, vehicle_id: str) -> list[ReleaseRecord]:
        return list(self.releases_by_vehicle.get(vehicle_id, []))


def _version_sort_key(version_number: str) -> tuple:
    if version_number == "NA":
        return (0,)
    try:
        parsed = Version(version_number)
        return (1, parsed.major, parsed.minor, parsed.micro)
    except InvalidVersion:
        return (2, version_number)
