import logging
import subprocess
import os.path

logger = logging.getLogger(__name__)


def is_git_repo(path: str) -> bool:
    """
    Check if a git repo exists at a given path

    Parameters:
        path (str): Path to the directory to check
    """
    if path is None:
        raise ValueError("path is required, cannot be None")

    if not os.path.exists(path=path):
        raise FileNotFoundError(f"The directory '{path}' does not exist.")

    if not os.path.isdir(s=path):
        # a file cannot be a git repository
        return False

    cmd = ['git', 'rev-parse', '--is-inside-work-tree']
    logger.debug(f"Running {' '.join(cmd)}")
    ret = subprocess.run(cmd, cwd=path, shell=False)
    return ret.returncode == 0


def is_valid_hex_string(test_str: str) -> bool:
    """
    Check if a string contains hexadecimal digits only

    Parameters:
        test_str (str): String to test
    """
    if test_str is None:
        raise ValueError("test_str cannot be None")

    return all(c in '1234567890abcdef' for c in test_str)
