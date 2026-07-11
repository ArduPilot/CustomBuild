from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseRecord:
    vehicle_id: str
    release_type: str
    version_number: str
    commit_reference: str
    ap_build_artifacts_url: str
