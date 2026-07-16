from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReleaseRecord:
    vehicle_id: str
    release_type: str
    version_number: str
    commit_reference: str


@dataclass(frozen=True)
class BoardArtifact:
    name: str
    url: str
    format: str
    size: Optional[int] = None
