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


def initialize_application(base_dir: str) -> None:
    """
    Initialize the application environment.

    Performs all necessary setup operations including creating the required
    directory structure.

    Args:
        base_dir: The base directory path (typically from CBS_BASEDIR)
    """
    if not base_dir:
        logger.warning("CBS_BASEDIR not set, skipping initialization")
        return

    logger.info(f"Initializing application with base directory: {base_dir}")

    ensure_base_structure(base_dir)

    logger.info("Application initialization complete")
