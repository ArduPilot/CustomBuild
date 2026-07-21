from unittest.mock import Mock, PropertyMock

import pytest

from metadata_manager import (
    DEFAULT_WHITELISTED_FORK_REMOTES,
    ForkRemoteSpec,
    ManifestJSON,
    ManifestJsonVersionsProvider,
    RemoteInfo,
    VehiclesManager,
    VersionInfo,
    VersionsManager,
)


@pytest.fixture
def vehicles_manager():
    existing = VehiclesManager.get_singleton()
    if existing is not None:
        return existing
    return VehiclesManager()


@pytest.fixture
def versions_manager(vehicles_manager, tmp_path):
    VersionsManager._VersionsManager__singleton = None
    repo = Mock()
    manager = VersionsManager(
        ap_repo=repo,
        remotes_json_path=str(tmp_path / "missing-remotes.json"),
        providers=[],
    )
    yield manager
    VersionsManager._VersionsManager__singleton = None


class TestManifestJsonVersionsProvider:
    def test_is_available_when_manifest_is_available(self, vehicles_manager):
        manifest_json = Mock(spec=ManifestJSON)
        type(manifest_json).is_available = PropertyMock(return_value=True)

        provider = ManifestJsonVersionsProvider(manifest_json)

        assert provider.is_available is True

    def test_is_unavailable_when_manifest_is_unavailable(self, vehicles_manager):
        manifest_json = Mock(spec=ManifestJSON)
        type(manifest_json).is_available = PropertyMock(return_value=False)

        provider = ManifestJsonVersionsProvider(manifest_json)

        assert provider.is_available is False
        assert provider.get_versions("copter") == []
        assert provider.get_remotes() == []

    def test_refresh_delegates_to_manifest_json(self, vehicles_manager):
        manifest_json = Mock(spec=ManifestJSON)
        provider = ManifestJsonVersionsProvider(manifest_json)

        provider.refresh()

        manifest_json.refresh.assert_called_once()


class TestVersionsManagerDedup:
    def _make_version(self, release_type: str, version_number: str, commit_ref: str):
        remote = RemoteInfo("ardupilot", "https://github.com/ardupilot/ardupilot.git")
        return VersionInfo(
            remote_info=remote,
            commit_ref=commit_ref,
            release_type=release_type,
            version_number=version_number,
            ap_build_artifacts_url=None,
        )

    def test_stable_wins_when_beta_is_seen_first(self, versions_manager):
        commit = "03c12698df56c600f5b3d39f8b17d414ea6d2a48"
        beta = self._make_version("beta", "4.5.0", commit)
        stable = self._make_version("stable", "4.5.0", commit)

        beta_provider = Mock()
        beta_provider.get_versions.return_value = [beta]
        stable_provider = Mock()
        stable_provider.get_versions.return_value = [stable]
        versions_manager._providers = [beta_provider, stable_provider]

        versions = versions_manager.get_versions_for_vehicle("sub")

        assert len(versions) == 1
        assert versions[0].release_type == "stable"
        assert versions[0].version_number == "4.5.0"

    def test_stable_wins_when_stable_is_seen_first(self, versions_manager):
        commit = "03c12698df56c600f5b3d39f8b17d414ea6d2a48"
        beta = self._make_version("beta", "4.5.0", commit)
        stable = self._make_version("stable", "4.5.0", commit)

        stable_provider = Mock()
        stable_provider.get_versions.return_value = [stable]
        beta_provider = Mock()
        beta_provider.get_versions.return_value = [beta]
        versions_manager._providers = [stable_provider, beta_provider]

        versions = versions_manager.get_versions_for_vehicle("sub")

        assert len(versions) == 1
        assert versions[0].release_type == "stable"

    def test_stable_wins_over_beta_with_same_number_different_commits(
        self, versions_manager
    ):
        beta = self._make_version("beta", "4.7.0", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        stable = self._make_version(
            "stable", "4.7.0", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )

        provider = Mock()
        provider.get_versions.return_value = [beta, stable]
        versions_manager._providers = [provider]

        versions = versions_manager.get_versions_for_vehicle("sub")

        assert len(versions) == 1
        assert versions[0].release_type == "stable"
        assert versions[0].version_number == "4.7.0"
        assert versions[0].commit_ref == stable.commit_ref

    def test_different_version_numbers_are_kept(self, versions_manager):
        stable = self._make_version(
            "stable", "4.6.0", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        beta = self._make_version(
            "beta", "4.7.0", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )

        provider = Mock()
        provider.get_versions.return_value = [stable, beta]
        versions_manager._providers = [provider]

        versions = versions_manager.get_versions_for_vehicle("sub")

        assert {v.version_number for v in versions} == {"4.6.0", "4.7.0"}

    def test_na_version_numbers_are_not_collapsed(self, versions_manager):
        latest_a = self._make_version(
            "latest", "NA", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        latest_b = self._make_version(
            "latest", "NA", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )

        provider = Mock()
        provider.get_versions.return_value = [latest_a, latest_b]
        versions_manager._providers = [provider]

        versions = versions_manager.get_versions_for_vehicle("sub")

        assert len(versions) == 2


class TestForkRemoteSpec:
    def test_default_rmackay9_uses_custom_repo_name(self):
        rmackay9 = next(
            spec for spec in DEFAULT_WHITELISTED_FORK_REMOTES if spec.owner == "rmackay9"
        )
        assert rmackay9.repo == "rmackay9-ardupilot"
        assert rmackay9.github_repo == "rmackay9/rmackay9-ardupilot"
        assert rmackay9.url == "https://github.com/rmackay9/rmackay9-ardupilot.git"

    def test_fork_remote_spec_url(self):
        spec = ForkRemoteSpec(owner="example", repo="my-ardupilot-fork")
        assert spec.github_repo == "example/my-ardupilot-fork"
        assert spec.url == "https://github.com/example/my-ardupilot-fork.git"
