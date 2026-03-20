"""
Application configuration and settings.
"""
import os
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional


logger = logging.getLogger(__name__)


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
    def enable_inbuilt_builder(self) -> bool:
        """Whether to enable the inbuilt builder."""
        return os.getenv('CBS_ENABLE_INBUILT_BUILDER', '1') == '1'

    @property
    def remote_reload_token(self) -> Optional[str]:
        """
        Get remote reload token from file or environment variable.

        Tries to read token from file first, falls back to environment variable.

        Returns:
            The authorization token if found, None otherwise
        """
        token_file_path = os.path.join(self.base_dir, 'secrets', 'reload_token')

        try:
            # Try to read the secret token from the file
            with open(token_file_path, 'r') as file:
                token = file.read().strip()
                return token
        except (FileNotFoundError, PermissionError):
            # If the file does not exist or no permission, check environment
            env_token = os.getenv('CBS_REMOTES_RELOAD_TOKEN', '')
            return env_token if env_token != '' else None
        except Exception as e:
            logger.error(
                f"Unexpected error reading token file at {token_file_path}: {e}. "
                "Checking environment for token."
            )
            # For any other error, fall back to environment variable
            env_token = os.getenv('CBS_REMOTES_RELOAD_TOKEN', None)
            return env_token if env_token != '' else None


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
