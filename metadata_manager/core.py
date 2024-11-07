import logging
import time
import os
import fnmatch
import ap_git
from . import exceptions as ex

logger = logging.getLogger(__name__)


class APSourceMetadataFetcher:
    """
    Class to fetch metadata like available boards, features etc.
    from the AP source code
    """

    __singleton = None

    def __init__(self, ap_repo_path: str) -> None:
        """
        Initializes the APSourceMetadataFetcher instance
        with a given repository path.

        Parameters:
            ap_repo_path (str): Path to the repository where
                                metadata scripts are located.

        Raises:
            TooManyInstancesError: If an instance of this class already exists,
                                   enforcing a singleton pattern.
        """
        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if APSourceMetadataFetcher.__singleton:
            raise ex.TooManyInstancesError()

        # Initialize the Git repository object pointing to the source repo.
        self.repo = ap_git.GitRepo(local_path=ap_repo_path)
        APSourceMetadataFetcher.__singleton = self

    def get_boards_at_commit(self, remote: str,
                             commit_ref: str) -> tuple:
        """
        Retrieves a list of boards available for building at a
        specified commit and returns the list and the default board.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            tuple: A tuple containing:
                - boards (list): A list of boards available at the
                                 specified commit.
                - default_board (str): The first board in the sorted list,
                                       designated as the default.
        """
        tstart = time.time()
        import importlib.util
        with self.repo.get_checkout_lock():
            self.repo.checkout_remote_commit_ref(
                remote=remote,
                commit_ref=commit_ref,
                force=True,
                hard_reset=True,
                clean_working_tree=True
            )
            spec = importlib.util.spec_from_file_location(
                name="board_list.py",
                location=os.path.join(
                    self.repo.get_local_path(),
                    'Tools', 'scripts',
                    'board_list.py')
                )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            all_boards = mod.AUTOBUILD_BOARDS
        exclude_patterns = ['fmuv*', 'SITL*']
        boards = []
        for b in all_boards:
            excluded = False
            for p in exclude_patterns:
                if fnmatch.fnmatch(b.lower(), p.lower()):
                    excluded = True
                    break
            if not excluded:
                boards.append(b)
        logger.debug(
            f"Took {(time.time() - tstart)} seconds to get boards"
        )
        boards.sort()
        default_board = boards[0]
        return (boards, default_board)

    def get_build_options_at_commit(self, remote: str,
                                    commit_ref: str) -> list:
        """
        Retrieves a list of build options available at a specified commit.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            list: A list of build options available at the specified commit.
        """
        tstart = time.time()
        import importlib.util
        with self.repo.get_checkout_lock():
            self.repo.checkout_remote_commit_ref(
                remote=remote,
                commit_ref=commit_ref,
                force=True,
                hard_reset=True,
                clean_working_tree=True
            )
            spec = importlib.util.spec_from_file_location(
                name="build_options.py",
                location=os.path.join(
                    self.repo.get_local_path(),
                    'Tools',
                    'scripts',
                    'build_options.py'
                )
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            build_options = mod.BUILD_OPTIONS
        logger.debug(
            f"Took {(time.time() - tstart)} seconds to get build options"
        )
        return build_options

    @staticmethod
    def get_singleton():
        return APSourceMetadataFetcher.__singleton
