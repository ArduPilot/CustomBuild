import logging
from typing import Optional

from .client import ManifestClient
from .exceptions import ManifestFetchError
from .index import ManifestIndex


class ManifestJSON:
    """Facade over cached manifest data for version and firmware-server lookups."""

    def __init__(self, url: str, cache_dir: str):
        self._client = ManifestClient(url=url, cache_dir=cache_dir)
        self._index: Optional[ManifestIndex] = None
        self.logger = logging.getLogger(__name__)

    @property
    def is_available(self) -> bool:
        return self._index is not None

    def refresh(self) -> None:
        try:
            manifest = self._client.fetch()
            self._index = ManifestIndex.build(manifest)
            self.logger.info(
                "Manifest index built with releases for %d vehicles",
                len(self._index.releases_by_vehicle),
            )
        except ManifestFetchError:
            if self._index is not None:
                self.logger.warning(
                    "Manifest refresh failed, continuing with stale index"
                )
                return
            raise

    def get_releases(self, vehicle_id: str) -> list:
        if not self.is_available:
            return []
        return self._index.get_releases(vehicle_id)
