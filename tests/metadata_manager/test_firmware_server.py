import json
from pathlib import Path
from unittest.mock import Mock, patch

from metadata_manager import ManifestClient, ManifestIndex
from metadata_manager.firmware_server.client import _CacheMeta


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MANIFEST = json.loads((FIXTURES_DIR / "manifest_sample.json").read_text())


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
            url="https://example.com/manifest.json",
            cache_dir=str(tmp_path),
        )
        client._write_cache(
            b'{"format-version":"1.0.0","firmware":[]}',
            _CacheMeta(etag='"abc"', last_modified="Mon, 01 Jan 2024 00:00:00 GMT"),
        )

        response = Mock(status_code=304, headers={}, content=b"")
        with patch("metadata_manager.firmware_server.client.requests.get", return_value=response):
            raw = client.fetch_raw()

        assert raw == b'{"format-version":"1.0.0","firmware":[]}'
