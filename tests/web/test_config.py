"""
Tests for the configuration module.
"""
import os
from unittest.mock import patch

from web.core.config import Settings


class TestSettings:
    """Test suite for Settings class."""

    def test_default_settings(self):
        """Test that default settings are initialized correctly."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.app_name == "CustomBuild API"
            assert settings.app_version == "1.0.0"
            assert settings.debug is False
            assert settings.redis_host == "localhost"
            assert settings.redis_port == "6379"
            assert settings.log_level == "INFO"
            assert settings.ap_git_url == "https://github.com/ardupilot/ardupilot.git"
            assert settings.enable_inbuilt_builder is True

    def test_env_var_overrides(self):
        """Test that environment variables override default settings."""
        env_overrides = {
            "CBS_BASEDIR": "/custom/base/path",
            "CBS_REDIS_HOST": "redis.example.com",
            "CBS_REDIS_PORT": "6380",
            "CBS_LOG_LEVEL": "DEBUG",
            "CBS_ENABLE_INBUILT_BUILDER": "0"
        }

        with patch.dict(os.environ, env_overrides, clear=True):
            settings = Settings()

            assert settings.base_dir == "/custom/base/path"
            assert settings.redis_host == "redis.example.com"
            assert settings.redis_port == "6380"
            assert settings.log_level == "DEBUG"
            assert settings.enable_inbuilt_builder is False


class TestRemoteReloadToken:
    """Test suite for remote_reload_token property."""

    def test_token_from_file(self, tmp_path):
        """Test that token is read from file when it exists."""
        secrets_dir = tmp_path / 'secrets'
        secrets_dir.mkdir()
        token_file = secrets_dir / 'reload_token'

        expected_token = "test-token-from-file"
        token_file.write_text(f"  {expected_token}  \n")  # Test whitespace stripping

        with patch.dict(os.environ, {"CBS_BASEDIR": str(tmp_path)}, clear=True):
            settings = Settings()
            assert settings.remote_reload_token == expected_token

    def test_token_file_takes_precedence_over_env(self, tmp_path):
        """Test that token from file takes precedence over environment variable."""
        secrets_dir = tmp_path / 'secrets'
        secrets_dir.mkdir()
        token_file = secrets_dir / 'reload_token'

        file_token = "token-from-file"
        env_token = "token-from-env"

        token_file.write_text(file_token)

        with patch.dict(os.environ, {
            "CBS_BASEDIR": str(tmp_path),
            "CBS_REMOTES_RELOAD_TOKEN": env_token
        }, clear=True):
            settings = Settings()
            assert settings.remote_reload_token == file_token

    def test_token_from_env_when_file_not_found(self, tmp_path):
        """Test that token falls back to environment variable when file doesn't exist."""
        expected_token = "test-token-from-env"

        with patch.dict(os.environ, {
            "CBS_BASEDIR": str(tmp_path),
            "CBS_REMOTES_RELOAD_TOKEN": expected_token
        }, clear=True):
            settings = Settings()
            assert settings.remote_reload_token == expected_token

    def test_token_from_env_on_file_read_error(self, tmp_path):
        """Test that token falls back to env var when file cannot be read."""
        env_token = "env-fallback-token"

        with patch.dict(os.environ, {
            "CBS_BASEDIR": str(tmp_path),
            "CBS_REMOTES_RELOAD_TOKEN": env_token
        }, clear=True):
            with patch("builtins.open", side_effect=PermissionError("No access")):
                settings = Settings()
                assert settings.remote_reload_token == env_token

    def test_token_none_when_not_configured(self, tmp_path):
        """Test that token is None when neither file nor env var is set."""
        with patch.dict(os.environ, {"CBS_BASEDIR": str(tmp_path)}, clear=True):
            settings = Settings()
            assert settings.remote_reload_token is None

    def test_token_none_when_env_is_empty_string(self, tmp_path):
        """Test that token is None when env var is empty string."""
        with patch.dict(os.environ, {
            "CBS_BASEDIR": str(tmp_path),
            "CBS_REMOTES_RELOAD_TOKEN": ""
        }, clear=True):
            settings = Settings()
            assert settings.remote_reload_token is None
