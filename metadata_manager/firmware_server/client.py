import json
import logging
import lzma
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from .exceptions import ManifestFetchError


@dataclass
class _CacheMeta:
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    fetched_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "etag": self.etag,
            "last_modified": self.last_modified,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "_CacheMeta":
        return cls(
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            fetched_at=data.get("fetched_at"),
        )


class ManifestClient:
    """Fetch and cache the ArduPilot firmware manifest.json.xz file."""

    def __init__(
        self,
        url: str,
        cache_dir: str,
        timeout: int = 120,
        user_agent: str = "CustomBuild/1.0",
    ):
        self.url = url
        self.cache_dir = Path(cache_dir)
        self.cache_path = self.cache_dir / "manifest.json"
        self.meta_path = self.cache_dir / "manifest.json.meta"
        self.timeout = timeout
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)

    def fetch_raw(self) -> bytes:
        headers = {"User-Agent": self.user_agent}
        meta = self._read_meta() if self._has_cache() else _CacheMeta()

        if meta.etag:
            headers["If-None-Match"] = meta.etag
        if meta.last_modified:
            headers["If-Modified-Since"] = meta.last_modified

        try:
            response = requests.get(
                self.url,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            return self._fallback_or_raise(exc)

        if response.status_code == 304:
            self.logger.info("Manifest not modified (304), using cache")
            self._touch_fetched_at(self._now_iso())
            return self._read_cache_bytes()

        if response.status_code != 200:
            return self._fallback_or_raise(
                ManifestFetchError(
                    f"Manifest fetch failed with status {response.status_code}"
                )
            )

        wire_bytes = response.content
        raw = lzma.decompress(wire_bytes)
        self._write_cache(
            raw,
            _CacheMeta(
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                fetched_at=self._now_iso(),
            ),
        )
        self.logger.info(
            "Downloaded manifest (%d wire bytes, %d decompressed bytes)",
            len(wire_bytes),
            len(raw),
        )
        return raw

    def fetch(self) -> dict:
        return json.loads(self.fetch_raw().decode("utf-8"))

    def _has_cache(self) -> bool:
        return self.cache_path.is_file()

    def _read_cache_bytes(self) -> bytes:
        return self.cache_path.read_bytes()

    def _read_meta(self) -> _CacheMeta:
        if not self.meta_path.is_file():
            return _CacheMeta()
        return _CacheMeta.from_dict(
            json.loads(self.meta_path.read_text(encoding="utf-8"))
        )

    def _write_cache(self, raw: bytes, meta: _CacheMeta) -> None:
        self._atomic_write_bytes(self.cache_path, raw)
        self._atomic_write_text(
            self.meta_path,
            json.dumps(meta.to_dict(), indent=2),
        )

    def _touch_fetched_at(self, fetched_at: str) -> None:
        meta = self._read_meta()
        meta.fetched_at = fetched_at
        self._atomic_write_text(
            self.meta_path,
            json.dumps(meta.to_dict(), indent=2),
        )

    def _atomic_write_bytes(self, path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_bytes(raw)
        os.replace(tmp_path, path)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)

    def _fallback_or_raise(self, exc: Exception) -> bytes:
        if self._has_cache():
            self.logger.warning(
                "Manifest fetch failed (%s), using stale cache", exc
            )
            return self._read_cache_bytes()
        raise ManifestFetchError(str(exc)) from exc

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
