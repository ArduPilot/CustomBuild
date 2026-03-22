"""
Pytest configuration and shared fixtures for end-to-end tests.

This module provides fixtures for setting up test environment including:
- Test client with FastAPI app
- Mock git repository
- Predefined remotes.json to avoid version fetching
- Remote reload authentication tokens
"""
import os
import json
import tempfile
import shutil
from typing import Generator
from unittest.mock import Mock, MagicMock

import pytest
from fastapi.testclient import TestClient


# Sample remotes.json for testing - no version fetching needed
TEST_REMOTES_JSON = [
    {
        "name": "test-remote-1",
        "url": "https://github.com/test/ardupilot.git",
        "vehicles": [
            {
                "name": "Copter",
                "releases": [
                    {
                        "release_type": "latest",
                        "version_number": "4.6.0",
                        "commit_reference": "refs/heads/master"
                    },
                    {
                        "release_type": "stable",
                        "version_number": "4.3.0",
                        "commit_reference": "refs/tags/Copter-4.3.0"
                    }
                ]
            },
            {
                "name": "Plane",
                "releases": [
                    {
                        "release_type": "latest",
                        "version_number": "4.5.0",
                        "commit_reference": "refs/heads/master"
                    }
                ]
            }
        ]
    },
    {
        "name": "test-remote-2",
        "url": "https://github.com/another/ardupilot.git",
        "vehicles": [
            {
                "name": "Rover",
                "releases": [
                    {
                        "release_type": "Custom",
                        "version_number": "Custom",
                        "commit_reference": "refs/tags/Rover-4.2.0"
                    }
                ]
            }
        ]
    }
]


@pytest.fixture(scope="session")
def test_base_dir() -> Generator[str, None, None]:
    """
    Create a temporary base directory structure for testing.

    Yields:
        str: Path to the temporary base directory
    """
    temp_dir = tempfile.mkdtemp(prefix="custombuild_test_")

    # Create required subdirectories
    subdirs = ["artifacts", "configs", "workdir", "secrets", "ardupilot"]
    for subdir in subdirs:
        os.makedirs(os.path.join(temp_dir, subdir), exist_ok=True)

    # Create remotes.json with test data
    remotes_json_path = os.path.join(temp_dir, "configs", "remotes.json")
    with open(remotes_json_path, "w") as f:
        json.dump(TEST_REMOTES_JSON, f, indent=2)

    # Create remote reload token file
    token_file_path = os.path.join(temp_dir, "secrets", "reload_token")
    with open(token_file_path, "w") as f:
        f.write("test-remote-reload-token-12345")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_git_repo():
    """
    Create a mock GitRepo object.

    Returns:
        Mock: Mock GitRepo instance
    """
    mock_repo = Mock()
    mock_repo.path = "/tmp/test/ardupilot"
    mock_repo.get_current_commit_hash.return_value = "abc123def456"
    mock_repo.checkout_commit.return_value = True
    mock_repo.get_tags.return_value = ["Copter-4.3.0", "Copter-4.4.0"]
    mock_repo.get_checkout_lock.return_value = MagicMock()
    return mock_repo


@pytest.fixture
def mock_ap_src_metadata_fetcher():
    """
    Create a mock APSourceMetadataFetcher for testing.

    Returns:
        Mock: Mock APSourceMetadataFetcher instance
    """
    return Mock()


@pytest.fixture
def mock_versions_fetcher(test_base_dir):
    """
    Create a mock VersionsFetcher that doesn't actually fetch versions.

    This allows tests to run without starting background threads or
    making actual git operations.

    Args:
        test_base_dir: Test base directory fixture

    Returns:
        Mock: Mock VersionsFetcher instance
    """
    from metadata_manager.versions_fetcher import RemoteInfo

    mock_fetcher = Mock()

    # Mock the reload_remotes_json method
    mock_fetcher.reload_remotes_json = Mock(return_value=None)

    # Mock get_all_remotes_info to return test remotes
    test_remotes = [
        RemoteInfo(name="test-remote-1", url="https://github.com/test/ardupilot.git"),
        RemoteInfo(name="test-remote-2", url="https://github.com/another/ardupilot.git")
    ]
    mock_fetcher.get_all_remotes_info = Mock(return_value=test_remotes)

    # Mock start/stop methods (no-op for tests)
    mock_fetcher.start = Mock()
    mock_fetcher.stop = Mock()

    return mock_fetcher


@pytest.fixture
def mock_build_manager():
    """
    Create a mock BuildManager for testing.

    Returns:
        Mock: Mock BuildManager instance
    """
    mock_manager = Mock()
    mock_manager.submit_build = Mock(return_value="test-build-id-123")
    mock_manager.get_build_progress = Mock(return_value={
        "build_id": "test-build-id-123",
        "status": "queued",
        "progress": 0
    })
    return mock_manager


@pytest.fixture
def mock_vehicles_manager():
    """
    Create a mock VehiclesManager for testing.

    Returns:
        Mock: Mock VehiclesManager instance
    """
    mock_manager = Mock()
    mock_manager.get_vehicle_names = Mock(return_value=["Copter", "Plane", "Rover"])
    return mock_manager


@pytest.fixture
def app_with_mocked_dependencies(
    test_base_dir,
    mock_git_repo,
    mock_versions_fetcher,
    mock_build_manager,
    mock_vehicles_manager,
):
    """
    Create a FastAPI app instance with mocked dependencies.

    This fixture sets up the application without requiring actual:
    - Git repository cloning
    - Version fetching background tasks
    - Redis connection
    - Build artifacts

    Args:
        test_base_dir: Test base directory
        mock_git_repo: Mock git repository
        mock_versions_fetcher: Mock versions fetcher
        mock_build_manager: Mock build manager
        mock_vehicles_manager: Mock vehicles manager

    Yields:
        FastAPI: Configured FastAPI application instance
    """
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.errors import RateLimitExceeded
    from web.api.v1 import router as v1_router
    from web.core.limiter import limiter, rate_limit_exceeded_handler

    # Set environment variables for test configuration
    os.environ["CBS_BASEDIR"] = test_base_dir
    os.environ["CBS_REDIS_HOST"] = "localhost"
    os.environ["CBS_REDIS_PORT"] = "6379"
    os.environ["CBS_ENABLE_INBUILT_BUILDER"] = "0"  # Disable builder for tests

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        """Test lifespan that doesn't start background tasks."""
        # Setup: Attach mocked dependencies to app state
        app.state.repo = mock_git_repo
        app.state.versions_fetcher = mock_versions_fetcher
        app.state.vehicles_manager = mock_vehicles_manager
        app.state.build_manager = mock_build_manager
        app.state.limiter = limiter

        # Create mock AP source metadata fetcher
        mock_ap_src_fetcher = Mock()
        app.state.ap_src_metadata_fetcher = mock_ap_src_fetcher

        # Don't start background tasks in test mode
        # versions_fetcher.start()
        # cleaner.start()
        # progress_updater.start()

        yield

        # Shutdown logic also skipped

    app = FastAPI(title="CustomBuild Test API", lifespan=test_lifespan)

    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.include_router(v1_router, prefix="/api")

    return app


@pytest.fixture
def client(app_with_mocked_dependencies) -> Generator[TestClient, None, None]:
    """
    Create a TestClient for making requests to the app.

    Args:
        app_with_mocked_dependencies: FastAPI app with mocked dependencies

    Yields:
        TestClient: Test client for making API requests
    """
    with TestClient(app_with_mocked_dependencies) as test_client:
        yield test_client
