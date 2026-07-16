import hashlib
from dataclasses import dataclass

from metadata_manager.firmware_server.models import ReleaseRecord


@dataclass(frozen=True)
class ForkRemoteSpec:
    """GitHub owner and repo for a whitelisted fork."""

    owner: str
    repo: str

    @property
    def github_repo(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.github_repo}.git"


@dataclass(frozen=True)
class RemoteInfo:
    name: str
    url: str

    def to_dict(self):
        return {
            "name": self.name,
            "url": self.url,
        }


class VersionInfo:
    """Version metadata exposed to the rest of the application."""

    def __init__(
        self,
        remote_info: RemoteInfo,
        commit_ref: str,
        release_type: str,
        version_number: str,
    ) -> None:
        self.remote_info = remote_info
        self.commit_ref = commit_ref
        self.release_type = release_type
        self.version_number = version_number

        commit_ref_sanitized = commit_ref.replace("/", "-")
        commit_ref_hash = hashlib.md5(commit_ref.encode()).hexdigest()[:8]
        self.version_id = (
            f"{remote_info.name}-{commit_ref_sanitized}-{commit_ref_hash}"
        )

    @classmethod
    def from_release_record(
        cls,
        remote_info: RemoteInfo,
        release: ReleaseRecord,
    ) -> "VersionInfo":
        return cls(
            remote_info=remote_info,
            commit_ref=release.commit_reference,
            release_type=release.release_type,
            version_number=release.version_number,
        )
