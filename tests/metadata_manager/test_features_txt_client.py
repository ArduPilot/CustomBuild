import requests
from unittest.mock import Mock, patch

import dill

from metadata_manager.firmware_server.features import (
    FeaturesTxtClient,
    parse_features_txt,
)


class TestParseFeaturesTxt:
    def test_parses_enabled_and_disabled_features(self):
        text = "\n".join([
            "HAL_LOGGING_ENABLED",
            "!HAL_PROFILER_ENABLED",
            "# comment",
            "",
            "AP_FENCE_ENABLED",
        ])
        assert parse_features_txt(text) == {
            "HAL_LOGGING_ENABLED": 1,
            "HAL_PROFILER_ENABLED": 0,
            "AP_FENCE_ENABLED": 1,
        }


class TestFeaturesTxtClient:
    def test_get_defaults_fetches_and_caches_with_etag(self):
        client = FeaturesTxtClient(caching_enabled=True)
        client._redis_client = Mock()
        client._redis_client.get.return_value = None
        response = Mock(
            status_code=200,
            text="HAL_LOGGING_ENABLED\n!HAL_PROFILER_ENABLED",
            headers={"ETag": '"abc"'},
        )
        response.raise_for_status = Mock()

        with patch(
            "metadata_manager.firmware_server.features.requests.get",
            return_value=response,
        ) as mock_get:
            result = client.get_defaults("https://example.com/features.txt")

        assert result == {
            "HAL_LOGGING_ENABLED": 1,
            "HAL_PROFILER_ENABLED": 0,
        }
        mock_get.assert_called_once()
        client._redis_client.set.assert_called_once()
        stored = dill.loads(client._redis_client.set.call_args.kwargs["value"])
        assert stored == {
            "etag": '"abc"',
            "defaults": result,
        }

    def test_get_defaults_skips_cache_without_etag(self):
        client = FeaturesTxtClient(caching_enabled=True)
        client._redis_client = Mock()
        client._redis_client.get.return_value = None
        response = Mock(status_code=200, text="HAL_LOGGING_ENABLED", headers={})
        response.raise_for_status = Mock()

        with patch(
            "metadata_manager.firmware_server.features.requests.get",
            return_value=response,
        ):
            result = client.get_defaults("https://example.com/features.txt")

        assert result == {"HAL_LOGGING_ENABLED": 1}
        client._redis_client.set.assert_not_called()

    def test_get_defaults_revalidates_cached_entry_with_if_none_match(self):
        client = FeaturesTxtClient(caching_enabled=True)
        client._redis_client = Mock()
        cached = {
            "etag": '"abc"',
            "defaults": {"HAL_LOGGING_ENABLED": 1},
        }
        client._redis_client.get.return_value = dill.dumps(cached)
        response = Mock(status_code=304, headers={})
        response.raise_for_status = Mock()

        with patch(
            "metadata_manager.firmware_server.features.requests.get",
            return_value=response,
        ) as mock_get:
            result = client.get_defaults("https://example.com/features.txt")

        assert result == cached["defaults"]
        mock_get.assert_called_once_with(
            "https://example.com/features.txt",
            headers={
                "User-Agent": "CustomBuild/1.0",
                "Accept-Encoding": "identity",
                "If-None-Match": '"abc"',
            },
            timeout=30,
        )
        client._redis_client.set.assert_not_called()

    def test_get_defaults_updates_cache_when_etag_changes(self):
        client = FeaturesTxtClient(caching_enabled=True)
        client._redis_client = Mock()
        cached = {
            "etag": '"old"',
            "defaults": {"OLD_FEATURE": 1},
        }
        client._redis_client.get.return_value = dill.dumps(cached)
        response = Mock(
            status_code=200,
            text="NEW_FEATURE\n!OLD_FEATURE",
            headers={"ETag": '"new"'},
        )
        response.raise_for_status = Mock()

        with patch(
            "metadata_manager.firmware_server.features.requests.get",
            return_value=response,
        ) as mock_get:
            result = client.get_defaults("https://example.com/features.txt")

        assert result == {"NEW_FEATURE": 1, "OLD_FEATURE": 0}
        mock_get.assert_called_once_with(
            "https://example.com/features.txt",
            headers={
                "User-Agent": "CustomBuild/1.0",
                "Accept-Encoding": "identity",
                "If-None-Match": '"old"',
            },
            timeout=30,
        )
        stored = dill.loads(client._redis_client.set.call_args.kwargs["value"])
        assert stored["etag"] == '"new"'
        assert stored["defaults"] == result

    def test_get_defaults_returns_none_on_fetch_failure(self):
        client = FeaturesTxtClient(caching_enabled=False)

        with patch(
            "metadata_manager.firmware_server.features.requests.get",
            side_effect=requests.RequestException("network error"),
        ):
            result = client.get_defaults("https://example.com/features.txt")

        assert result is None

    def test_get_defaults_does_not_cache_failure_when_caching_enabled(self):
        client = FeaturesTxtClient(caching_enabled=True)
        client._redis_client = Mock()
        client._redis_client.get.return_value = None

        with patch(
            "metadata_manager.firmware_server.features.requests.get",
            side_effect=requests.RequestException("network error"),
        ):
            result = client.get_defaults("https://example.com/missing/features.txt")

        assert result is None
        client._redis_client.set.assert_not_called()
