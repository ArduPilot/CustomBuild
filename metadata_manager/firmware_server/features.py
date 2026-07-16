import logging

import dill
import redis
import requests

FEATURES_CACHE_TTL_SEC = 86400


def parse_features_txt(text: str) -> dict:
    """Parse features.txt content into a define to state mapping."""
    feature_states = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line[0] == "!":
            feature_name, state = line[1:], 0
        else:
            feature_name, state = line, 1
        feature_states[feature_name] = state
    return feature_states


class FeaturesTxtClient:
    """Fetch and cache board default features from firmware-server features.txt."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: str = "6379",
        caching_enabled: bool = True,
        timeout: int = 30,
        user_agent: str = "CustomBuild/1.0",
    ):
        self.caching_enabled = caching_enabled
        self.timeout = timeout
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        self._cache_key_prefix = "features-"

        if self.caching_enabled:
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=False,
            )

    def _cache_key(self, url: str) -> str:
        return self._cache_key_prefix + url

    def _get_from_cache(self, url: str) -> tuple[str | None, dict | None]:
        if not self.caching_enabled:
            return None, None
        value = self._redis_client.get(self._cache_key(url))
        if value is None:
            return None, None
        entry = dill.loads(value)
        if not isinstance(entry, dict):
            return None, None
        etag = entry.get("etag")
        defaults = entry.get("defaults")
        if not etag or defaults is None:
            return None, None
        return etag, defaults

    def _store_in_cache(self, url: str, etag: str, defaults: dict) -> None:
        if not self.caching_enabled:
            return
        self._redis_client.set(
            name=self._cache_key(url),
            value=dill.dumps({"etag": etag, "defaults": defaults}),
            ex=FEATURES_CACHE_TTL_SEC,
        )

    def get_defaults(self, url: str) -> dict | None:
        """
        Fetch and parse features.txt for the given URL.

        Returns a mapping of feature define to state (1 enabled, 0 disabled),
        or None if the fetch fails.
        """
        cached_etag, cached_defaults = self._get_from_cache(url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "identity",
        }
        if cached_etag:
            headers["If-None-Match"] = cached_etag

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code == 304:
                return cached_defaults
            response.raise_for_status()
            defaults = parse_features_txt(response.text)
            enabled_count = sum(1 for state in defaults.values() if state)
            disabled_count = len(defaults) - enabled_count
            self.logger.info(
                "Fetched board defaults from firmware server: "
                "%d enabled, %d disabled",
                enabled_count,
                disabled_count,
            )
            etag = response.headers.get("ETag")
            if etag:
                self._store_in_cache(url, etag, defaults)
            return defaults
        except requests.RequestException as exc:
            self.logger.warning(
                "Failed to fetch board defaults from %s: %s", url, exc
            )
            return None
