import json
import lzma
from pathlib import Path
from unittest.mock import Mock, patch

from metadata_manager import ManifestClient, ManifestIndex, ManifestJSON
from metadata_manager.firmware_server.client import _CacheMeta
from metadata_manager.firmware_server.index import latest_features_txt_url


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MANIFEST = json.loads((FIXTURES_DIR / "manifest_sample.json").read_text())
SAMPLE_JSON_BYTES = json.dumps(SAMPLE_MANIFEST).encode("utf-8")
MANIFEST_XZ_URL = "https://firmware.ardupilot.org/manifest.json.xz"


class TestManifestIndex:
    def test_builds_releases_for_copter_heli_and_tracker(self):
        index = ManifestIndex.build(SAMPLE_MANIFEST)

        copter = index.get_releases("copter")
        stable = [r for r in copter if r.release_type == "stable" and r.version_number == "4.6.3"]
        assert len(stable) == 1
        assert stable[0].commit_reference.startswith("aaaa")

        heli = index.get_releases("heli")
        heli_stable = [r for r in heli if r.release_type == "stable" and r.version_number == "4.6.3"]
        assert len(heli_stable) == 1
        assert heli_stable[0].commit_reference.startswith("bbbb")

        tracker = index.get_releases("tracker")
        assert any(r.version_number == "4.6.3" for r in tracker)

        latest = [r for r in copter if r.release_type == "latest"]
        assert len(latest) == 1
        assert latest[0].commit_reference.startswith("eeee")
        assert latest[0].version_number == "NA"

    def test_indexes_board_artifacts_for_vehicle_version_board(self):
        index = ManifestIndex.build(SAMPLE_MANIFEST)

        copter_artifacts = index.get_board_artifacts(
            "copter", "stable", "4.6.3", "CubeOrange"
        )
        assert len(copter_artifacts) == 1
        assert copter_artifacts[0].name == "arducopter.apj"
        assert copter_artifacts[0].format == "apj"
        assert copter_artifacts[0].url.endswith("/Copter/stable-4.6.3/CubeOrange/arducopter.apj")

        heli_artifacts = index.get_board_artifacts(
            "heli", "stable", "4.6.3", "CubeOrange"
        )
        assert len(heli_artifacts) == 1
        assert heli_artifacts[0].name == "arducopter-heli.apj"

        latest_artifacts = index.get_board_artifacts(
            "copter", "latest", "NA", "CubeOrange"
        )
        assert len(latest_artifacts) == 1
        assert latest_artifacts[0].url.endswith("/Copter/latest/CubeOrange/arducopter.apj")

    def test_board_artifacts_dedupe_generic_stable_alias(self):
        index = ManifestIndex.build(SAMPLE_MANIFEST)

        copter_artifacts = index.get_board_artifacts(
            "copter", "stable", "4.6.3", "CubeOrange"
        )
        assert len(copter_artifacts) == 1
        assert copter_artifacts[0].url.endswith("/Copter/stable-4.6.3/CubeOrange/arducopter.apj")

        heli_artifacts = index.get_board_artifacts(
            "heli", "stable", "4.6.3", "CubeOrange"
        )
        assert len(heli_artifacts) == 1
        assert heli_artifacts[0].name == "arducopter-heli.apj"

        latest_artifacts = index.get_board_artifacts(
            "copter", "latest", "NA", "CubeOrange"
        )
        assert len(latest_artifacts) == 1
        assert latest_artifacts[0].url.endswith("/Copter/latest/CubeOrange/arducopter.apj")

    def test_board_artifacts_missing_returns_empty_list(self):
        index = ManifestIndex.build(SAMPLE_MANIFEST)

        assert index.get_board_artifacts("copter", "stable", "4.6.3", "UnknownBoard") == []

    def test_get_features_txt_url_from_manifest_artifact(self):
        index = ManifestIndex.build(SAMPLE_MANIFEST)

        url = index.get_features_txt_url("copter", "stable", "4.6.3", "CubeOrange")
        assert url == (
            "https://firmware.ardupilot.org/Copter/stable-4.6.3/"
            "CubeOrange/features.txt"
        )

        heli_url = index.get_features_txt_url("heli", "stable", "4.6.3", "CubeOrange")
        assert heli_url == (
            "https://firmware.ardupilot.org/Copter/stable-4.6.3/"
            "CubeOrange-heli/features.txt"
        )

    def test_get_features_txt_url_missing_board_returns_none(self):
        index = ManifestIndex.build(SAMPLE_MANIFEST)

        assert index.get_features_txt_url(
            "copter", "stable", "4.6.3", "UnknownBoard"
        ) is None


class TestLatestFeaturesTxtUrl:
    def test_copter_board(self):
        assert latest_features_txt_url("copter", "CubeOrange") == (
            "https://firmware.ardupilot.org/Copter/latest/CubeOrange/features.txt"
        )

    def test_heli_board(self):
        assert latest_features_txt_url("heli", "CubeOrange") == (
            "https://firmware.ardupilot.org/Copter/latest/CubeOrange-heli/features.txt"
        )


class TestManifestJSONFeaturesUrl:
    def test_tag_release_uses_latest_url(self):
        manifest_json = ManifestJSON(url="https://example.com/manifest.json", cache_dir="/tmp")
        assert manifest_json.get_features_txt_url(
            "copter", "tag", "my-feature", "CubeOrange"
        ) == latest_features_txt_url("copter", "CubeOrange")

    def test_stable_release_uses_manifest_index(self):
        manifest_json = ManifestJSON(url="https://example.com/manifest.json", cache_dir="/tmp")
        manifest_json._index = ManifestIndex.build(SAMPLE_MANIFEST)

        assert manifest_json.get_features_txt_url(
            "copter", "stable", "4.6.3", "CubeOrange"
        ) == (
            "https://firmware.ardupilot.org/Copter/stable-4.6.3/"
            "CubeOrange/features.txt"
        )

    def test_unavailable_manifest_returns_none_for_stable(self):
        manifest_json = ManifestJSON(url="https://example.com/manifest.json", cache_dir="/tmp")
        assert manifest_json.get_features_txt_url(
            "copter", "stable", "4.6.3", "CubeOrange"
        ) is None


class TestManifestClientCache:
    def test_uses_cache_on_304(self, tmp_path):
        client = ManifestClient(
            url=MANIFEST_XZ_URL,
            cache_dir=str(tmp_path),
        )
        client._write_cache(
            b'{"format-version":"1.0.0","firmware":[]}',
            _CacheMeta(etag='"abc"', last_modified="Mon, 01 Jan 2024 00:00:00 GMT"),
        )

        response = Mock(status_code=304, headers={}, content=b"")
        with patch(
            "metadata_manager.firmware_server.client.requests.get",
            return_value=response,
        ) as mock_get:
            raw = client.fetch_raw()

        assert raw == b'{"format-version":"1.0.0","firmware":[]}'
        mock_get.assert_called_once_with(
            MANIFEST_XZ_URL,
            headers={
                "User-Agent": "CustomBuild/1.0",
                "If-None-Match": '"abc"',
                "If-Modified-Since": "Mon, 01 Jan 2024 00:00:00 GMT",
            },
            timeout=120,
        )

    def test_download_decompresses_xz_manifest(self, tmp_path):
        client = ManifestClient(
            url=MANIFEST_XZ_URL,
            cache_dir=str(tmp_path),
        )
        compressed = lzma.compress(SAMPLE_JSON_BYTES)
        response = Mock(
            status_code=200,
            content=compressed,
            headers={
                "ETag": '"etag123"',
                "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            },
        )
        response.raise_for_status = Mock()

        with patch(
            "metadata_manager.firmware_server.client.requests.get",
            return_value=response,
        ):
            result = client.fetch()

        assert result == SAMPLE_MANIFEST
        assert client.cache_path.read_bytes() == SAMPLE_JSON_BYTES
        meta = _CacheMeta.from_dict(
            json.loads(client.meta_path.read_text(encoding="utf-8"))
        )
        assert meta.etag == '"etag123"'
        assert meta.last_modified == "Mon, 01 Jan 2024 00:00:00 GMT"
