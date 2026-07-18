import json
import lzma
from pathlib import Path
from unittest.mock import Mock, patch

from metadata_manager import ManifestClient, ManifestIndex
from metadata_manager.firmware_server.client import _CacheMeta


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
        assert latest[0].ap_build_artifacts_url == (
            "https://firmware.ardupilot.org/Copter/latest"
        )


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
