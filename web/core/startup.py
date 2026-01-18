"""
Application startup utilities.

Handles initial setup of required directories and configuration files.
This module ensures the application environment is properly configured
before the main application starts.
"""
import os
import logging

logger = logging.getLogger(__name__)


def ensure_base_structure(base_dir: str) -> None:
    """
    Ensure required base directory structure exists.

    Creates necessary subdirectories for artifacts, configs, workdir,
    and secrets if they don't already exist.

    Args:
        base_dir: The base directory path (typically from CBS_BASEDIR)
    """
    if not base_dir:
        logger.warning("Base directory not specified, skipping initialization")
        return

    # Define required subdirectories
    subdirs = [
        'artifacts',
        'configs',
        'workdir',
        'secrets',
    ]

    for subdir in subdirs:
        path = os.path.join(base_dir, subdir)
        os.makedirs(path, exist_ok=True)
        logger.debug(f"Ensured directory exists: {path}")


def ensure_remotes_json(base_dir: str, remote_name: str = "ardupilot") -> None:
    """
    Ensure remotes.json configuration file exists.

    If the remotes.json file doesn't exist, creates it by fetching release
    information from the specified remote.

    Args:
        base_dir: The base directory path (typically from CBS_BASEDIR)
        remote_name: The remote repository name to fetch releases from
    """
    if not base_dir:
        logger.warning(
            "Base directory not specified, "
            "skipping remotes.json initialization"
        )
        return

    remotes_json_path = os.path.join(base_dir, 'configs', 'remotes.json')

    if not os.path.isfile(remotes_json_path):
        logger.info(
            f"remotes.json not found at {remotes_json_path}, "
            f"creating it..."
        )
        try:
            from scripts import fetch_releases
            fetch_releases.run(
                base_dir=base_dir,
                remote_name=remote_name,
            )
            logger.info("Successfully created remotes.json")
        except Exception as e:
            logger.error(f"Failed to create remotes.json: {e}")
            raise
    else:
        logger.debug(f"remotes.json already exists at {remotes_json_path}")


def initialize_application(base_dir: str) -> None:
    """
    Initialize the application environment.

    Performs all necessary setup operations including:
    - Creating required directory structure
    - Ensuring remotes.json configuration exists

    Args:
        base_dir: The base directory path (typically from CBS_BASEDIR)
    """
    if not base_dir:
        logger.warning("CBS_BASEDIR not set, skipping initialization")
        return

    logger.info(f"Initializing application with base directory: {base_dir}")

    # Ensure directory structure
    ensure_base_structure(base_dir)

    # Ensure remotes.json exists
    ensure_remotes_json(base_dir)

    logger.info("Application initialization complete")
