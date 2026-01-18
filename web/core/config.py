"""
Application configuration and settings.
"""
import os
from pathlib import Path
from functools import lru_cache


class Settings:
    """Application settings."""

    def __init__(self):
        # Application
        self.app_name: str = "CustomBuild API"
        self.app_version: str = "1.0.0"
        self.debug: bool = False

        # Paths
        self.base_dir: str = os.getenv(
            "CBS_BASEDIR",
            default=str(Path(__file__).parent.parent.parent.parent / "base")
        )

        # Redis
        self.redis_host: str = os.getenv(
            'CBS_REDIS_HOST',
            default='localhost'
        )
        self.redis_port: str = os.getenv(
            'CBS_REDIS_PORT',
            default='6379'
        )

        # Logging
        self.log_level: str = os.getenv('CBS_LOG_LEVEL', default='INFO')

        # ArduPilot Git Repository
        self.ap_git_url: str = "https://github.com/ardupilot/ardupilot.git"

    @property
    def source_dir(self) -> str:
        """ArduPilot source directory."""
        return os.path.join(self.base_dir, 'ardupilot')

    @property
    def artifacts_dir(self) -> str:
        """Build artifacts directory."""
        return os.path.join(self.base_dir, 'artifacts')

    @property
    def outdir_parent(self) -> str:
        """Build output directory (same as artifacts_dir)."""
        return self.artifacts_dir

    @property
    def workdir_parent(self) -> str:
        """Work directory parent."""
        return os.path.join(self.base_dir, 'workdir')

    @property
    def remotes_json_path(self) -> str:
        """Path to remotes.json configuration."""
        return os.path.join(self.base_dir, 'configs', 'remotes.json')

    @property
    def admin_token_file_path(self) -> str:
        """Path to admin token secret file."""
        return os.path.join(self.base_dir, 'secrets', 'reload_token')

    @property
    def enable_inbuilt_builder(self) -> bool:
        """Whether to enable the inbuilt builder."""
        return os.getenv('CBS_ENABLE_INBUILT_BUILDER', '1') == '1'

    @property
    def admin_token_env(self) -> str:
        """Token required to reload remotes.json via API."""
        env = os.getenv('CBS_REMOTES_RELOAD_TOKEN', '')
        return env if env != '' else None


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
