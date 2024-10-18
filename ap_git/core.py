import logging
import subprocess
from threading import RLock
from . import utils
from . import exceptions as ex

logger = logging.getLogger(__name__)


class GitRepo:
    """
    Class to handle Git operations in a local Git repository.
    """

    __checkout_locks = dict()

    def __init__(self, local_path: str) -> None:
        """
        Initialize GitRepo with the path to the local Git repository.

        Parameters:
            local_path (str): Path to the Git repository
        """
        self.__set_local_path(local_path=local_path)
        self.__register_lock()
        logger.info(f"GitRepo initialised for {local_path}")

    def __eq__(self, other) -> bool:
        """
        Check if the instance is equal to the 'other' instance

        Parameters:
            other: the other Object to check
        """
        if type(other) is type(self):
            # return True if the paths of the repositories the objects
            # point to are equal, otherwise False
            return self.__local_path == other.__local_path

        return False

    def __hash__(self) -> int:
        """
        Return the hash value of the instance
        """
        return hash(self.__local_path)

    def __register_lock(self) -> None:
        """
        Initialize an RLock object for the instance in a shared dictionary
        """
        if not GitRepo.__checkout_locks.get(self):
            # create a Lock object for the instance, if is not already created
            GitRepo.__checkout_locks[self] = RLock()

        return

    def __set_local_path(self, local_path: str) -> None:
        """
        Set the path for the repository, ensuring it is a valid Git repo.

        Parameters:
            local_path (str): Path to the Git repository

        Raises:
            NonGitDirectoryError: If the directory is not a valid
                                  Git repository
        """
        if not utils.is_git_repo(local_path):
            raise ex.NonGitDirectoryError(directory=local_path)

        self.__local_path = local_path

    def get_local_path(self) -> str:
        """
        Return the local path of the repository.

        Returns:
            str: Path to the Git repository
        """
        return self.__local_path

    def get_checkout_lock(self) -> RLock:
        """
        Return the checkout lock object associated with the instance

        Returns:
            RLock: The lock object associated with the instance
        """
        lock = GitRepo.__checkout_locks.get(self)
        if lock is None:
            raise ex.LockNotInitializedError(
                lock_name="checkout_lock",
                path=self.__local_path
            )
        return lock

    def __checkout(self, commit_ref: str, force: bool = False) -> None:
        """
        Check out a specific commit.

        Parameters:
            commit_ref (str): Commit reference to check out
            force (bool): Force checkout (default is False)

        Raises:
            ValueError: If commit_ref is None
        """
        if commit_ref is None:
            raise ValueError("commit_ref is required, cannot be None.")

        cmd = ['git', 'checkout', commit_ref]

        if force:
            cmd.append('-f')

        logger.debug(f"Running {' '.join(cmd)}")
        logger.debug("Attempting to aquire checkout lock.")
        with self.get_checkout_lock():
            subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    def __reset(self, commit_ref: str, hard: bool = False) -> None:
        """
        Reset to a specific commit.

        Parameters:
            commit_ref (str): Commit reference to reset to
            hard (bool): Use hard reset (default is False)

        Raises:
            ValueError: If commit_ref is None
        """
        if commit_ref is None:
            raise ValueError("commit_ref is required, cannot be None.")

        cmd = ['git', 'reset', commit_ref]

        if hard:
            cmd.append('--hard')
        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    def __force_recursive_clean(self) -> None:
        """
        Forcefully clean the working directory,
        removing untracked files and directories.
        """
        cmd = ['git', 'clean', '-xdff']
        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    def __remote_list(self) -> list[str]:
        """
        Retrieve a list of remotes added to the repository

        Returns:
            list[str]: List of remote names
        """
        cmd = ['git', 'remote']

        logger.debug(f"Running {' '.join(cmd)}")
        ret = subprocess.run(
            cmd, cwd=self.__local_path, shell=False, capture_output=True,
            encoding='utf-8', check=True
        )
        return ret.stdout.split('\n')[:-1]

    def __is_commit_present_locally(self, commit_ref: str) -> bool:
        """
        Check if a specific commit exists locally.

        Parameters:
            commit_ref (str): Commit hash to check

        Returns:
            bool: True if the commit exists locally, False otherwise
        """
        if commit_ref is None:
            raise ValueError("commit_ref is required, cannot be None.")

        cmd = ['git', 'diff-tree', commit_ref, '--no-commit-id', '--no-patch']
        logger.debug(f"Running {' '.join(cmd)}")
        ret = subprocess.run(cmd, cwd=self.__local_path, shell=False)
        return ret.returncode == 0

    def remote_set_url(self, remote: str, url: str) -> None:
        """
        Set the URL for a specific remote.

        Parameters:
            remote (str): Name of the remote
            url (str): URL to set for the remote

        Raises:
            ValueError: If remote or URL is None
        """
        if remote is None:
            raise ValueError("remote is required, cannot be None.")

        if url is None:
            raise ValueError("url is required, cannot be None.")

        cmd = ['git', 'remote', 'set-url', remote, url]
        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, check=True)

    def fetch_remote(self, remote: str, force: bool = False,
                     tags: bool = False, recurse_submodules: bool = False,
                     refetch: bool = False) -> None:
        """
        Fetch updates from a remote repository.

        Parameters:
            remote (str): Remote to fetch from; if None, fetches all
            force (bool): Force fetch (default is False)
            tags (bool): Fetch tags (default is False)
            recurse_submodules (bool): Recurse into submodules
                                       (default is False)
            refetch (bool): Re-fetch all objects (default is False)
        """
        cmd = ['git', 'fetch']

        if remote:
            cmd.append(remote)
        else:
            logger.info("fetch_remote: remote is None, fetching all remotes")
            cmd.append('--all')

        if force:
            cmd.append('--force')

        if tags:
            cmd.append('--tags')

        if refetch:
            cmd.append('--refetch')

        if recurse_submodules:
            cmd.append('--recurse-submodules')
        else:
            cmd.append('--no-recurse-submodules')

        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False)

    def __branch_create(self, branch_name: str,
                        start_point: str = None) -> None:
        """
        Create a new branch starting from a given commit.

        Parameters:
            branch_name (str): Name of the branch to create
            start_point (str): Starting commit or branch (optional)
        """
        if branch_name is None:
            raise ValueError("branch_name is required, cannot be None.")

        cmd = ['git', 'branch', branch_name]

        if start_point:
            if not self.__is_commit_present_locally(commit_ref=start_point):
                raise ex.CommitNotFoundError(commit_ref=start_point)
            cmd.append(start_point)

        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    def __branch_delete(self, branch_name: str, force: bool = False) -> None:
        """
        Delete a local branch.

        Parameters:
            branch_name (str): Name of the branch to delete
            force (bool): Force delete (default is False)
        """
        if branch_name is None:
            raise ValueError("branch_name is required, cannot be None.")

        if not self.__is_commit_present_locally(commit_ref=branch_name):
            raise ex.CommitNotFoundError(commit_ref=branch_name)

        cmd = ['git', 'branch', '-d', branch_name]

        if force:
            cmd.append('--force')

        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    def commit_id_for_remote_ref(self, remote: str,
                                 commit_ref: str) -> str:
        """
        Get the commit ID for a specific commit reference from a remote.

        Parameters:
            remote (str): Name of the remote
            commit_ref (str): Reference to get the commit ID for

        Returns:
            str | None: Commit ID if found, None otherwise
        """
        if remote is None:
            raise ValueError("remote is required, cannot be None.")

        if remote not in self.__remote_list():
            raise ex.RemoteNotFoundError(remote=remote)

        if commit_ref is None:
            raise ValueError("commit_ref is required, cannot be None.")

        if utils.is_valid_hex_string(test_str=commit_ref):
            # skip conversion if commit_ref is already hex string
            return commit_ref

        # allow branches and tags only for now
        allowed_ref_types = ['tags', 'heads']
        split_ref = commit_ref.split('/', 2)

        if len(split_ref) != 3 or split_ref[0] != 'refs':
            raise ValueError(f"commit_ref '{commit_ref}' format is invalid.")

        _, ref_type, _ = split_ref

        if ref_type not in allowed_ref_types:
            raise ValueError(f"ref_type '{ref_type}' is not supported.")

        cmd = ['git', 'ls-remote', remote]

        logger.debug(f"Running {' '.join(cmd)}")
        ret = subprocess.run(
            cmd, cwd=self.__local_path, encoding='utf-8', capture_output=True,
            shell=False, check=True
        )

        for line in ret.stdout.split('\n')[:-1]:
            (commit_id, res_ref) = line.split('\t')
            if res_ref == commit_ref:
                return commit_id

        return None

    def __ensure_commit_fetched(self, remote: str, commit_id: str) -> None:
        """
        Ensure a specific commit is fetched from the remote repository.

        Parameters:
            remote (str): Remote name to fetch from
            commit_id (str): Commit ID to ensure it is available locally

        Raises:
            RemoteNotFoundError: If the specified remote does not exist
            CommitNotFoundError: If the commit cannot be fetched after
                                 multiple attempts
        """
        if remote is None:
            raise ValueError("remote is required, cannot be None.")

        if remote not in self.__remote_list():
            raise ex.RemoteNotFoundError(remote=remote)

        if commit_id is None:
            raise ValueError("commit_id is required, cannot be None.")

        if not utils.is_valid_hex_string(test_str=commit_id):
            raise ValueError(
                f"commit_id should be a hex string, got '{commit_id}'."
            )

        if self.__is_commit_present_locally(commit_ref=commit_id):
            # early return if commit is already fetched
            return

        self.fetch_remote(remote=remote, force=True, tags=True)

        # retry fetch with refetch option if the commit is still not found
        if not self.__is_commit_present_locally(commit_ref=commit_id):
            self.fetch_remote(
                remote=remote, force=True, tags=True, refetch=True
            )

        if not self.__is_commit_present_locally(commit_ref=commit_id):
            raise ex.CommitNotFoundError(commit_ref=commit_id)

    def checkout_remote_commit_ref(self, remote: str,
                                   commit_ref: str,
                                   force: bool = False,
                                   hard_reset: bool = False,
                                   clean_working_tree: bool = False) -> None:
        """
        Check out a specific commit from a remote repository.

        Parameters:
            remote (str): Remote name to check out from
            commit_ref (str): Commit reference to check out
            force (bool): Force the checkout (default is False)
            hard_reset (bool): Hard reset after checkout (default is False)
            clean_working_tree (bool): Clean untracked files after checkout
                                       (default is False)

        Raises:
            RemoteNotFoundError: If the specified remote does not exist
            CommitNotFoundError: If the specified commit cannot be found
        """
        if remote is None:
            logger.error("remote cannot be None for checkout to remote commit")
            raise ValueError("remote is required, cannot be None.")

        if remote not in self.__remote_list():
            raise ex.RemoteNotFoundError(remote=remote)

        if commit_ref is None:
            raise ValueError("commit_ref is required, cannot be None.")

        # retrieve the commit ID for the specified commit reference
        commit_id = self.commit_id_for_remote_ref(
            remote=remote, commit_ref=commit_ref
        )

        # ensure the commit is fetched from the remote repository
        self.__ensure_commit_fetched(remote=remote, commit_id=commit_id)

        # perform checkout on the specified commit using the commit ID
        # commit ID is used in place of branch name or tag name to make sure
        # do not check out the branch or tag from wrong remote
        self.__checkout(commit_ref=commit_id, force=force)

        # optional hard reset and clean of working tree after checkout
        if hard_reset:
            self.__reset(commit_ref=commit_id, hard=True)

        if clean_working_tree:
            self.__force_recursive_clean()

    def submodule_update(self, init: bool = False, recursive: bool = False,
                         force: bool = False) -> None:
        """
        Update Git submodules for the repository.

        Parameters:
            init (bool): Initialize submodules if they are not initialized
                         (default is False)
            recursive (bool): Update submodules recursively (default is False)
            force (bool): Force update even if there are changes
                          (default is False)
        """
        cmd = ['git', 'submodule', 'update']

        if init:
            cmd.append('--init')

        if recursive:
            cmd.append('--recursive')

        if force:
            cmd.append('--force')

        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    def remote_add(self, remote: str, url: str) -> None:
        """
        Add a new remote to the Git repository.

        Parameters:
            remote (str): Name of the remote to add
            url (str): URL for the remote repository

        Raises:
            DuplicateRemoteError: If remote already exists and
                                  overwrite is not allowed
        """
        if remote is None:
            raise ValueError("remote is required, cannot be None.")

        if url is None:
            raise ValueError("url is required, cannot be None.")

        # Set the URL if the remote exists and overwrite is allowed
        if remote in self.__remote_list():
            raise ex.DuplicateRemoteError(remote)

        # Add the new remote
        cmd = ['git', 'remote', 'add', remote, url]
        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.__local_path, shell=False, check=True)

    @staticmethod
    def clone(source: str,
              dest: str,
              branch: str = None,
              single_branch: bool = False,
              recurse_submodules: bool = False,
              shallow_submodules: bool = False) -> "GitRepo":
        """
        Clone a Git repository.

        Parameters:
            source (str): Source path of the repository to clone
                          Can be local or a url.
            dest (str): Destination path for the clone
            branch (str): Specific branch to clone (optional)
            single_branch (bool): Only clone a single branch (default is False)
            recurse_submodules (bool): Recurse into submodules
                                       (default is False)
            shallow_submodules (bool): any cloned submodules will be shallow

        Returns:
            GitRepo: the cloned git repository
        """
        cmd = ['git', 'clone', source, dest]

        if branch:
            cmd.append('--branch=' + branch)

        if single_branch:
            cmd.append('--single-branch')

        if recurse_submodules:
            cmd.append('--recurse-submodules')

        if shallow_submodules:
            cmd.append('--shallow-submodules')

        logger.debug(f"Running {' '.join(cmd)}")
        subprocess.run(cmd, shell=False, check=True)

        return GitRepo(local_path=dest)

    @staticmethod
    def shallow_clone_at_commit_from_local(source: str,
                                           remote: str,
                                           commit_ref: str,
                                           dest: str) -> "GitRepo":
        """
        Perform a shallow clone of a repository at a specific commit.

        Parameters:
            source (str): Source path of the local repository
            remote (str): Remote name containing the commit
            commit_ref (str): Commit reference to clone
            dest (str): Destination path for the clone

        Returns:
            GitRepo: the cloned git repository

        Raises:
            RemoteNotFoundError: If the specified remote does not exist
            CommitNotFoundError: If the specified commit cannot be found
        """
        if remote is None:
            raise ValueError("remote is required, cannot be None.")

        if commit_ref is None:
            raise ValueError("commit_ref is required, cannot be None.")

        source_repo = GitRepo(local_path=source)

        # get the commit ID for the specified remote reference
        commit_id = source_repo.commit_id_for_remote_ref(
            remote=remote, commit_ref=commit_ref
        )
        source_repo.__ensure_commit_fetched(remote=remote, commit_id=commit_id)

        # create a temporary branch to point to the specified commit
        # as shallow clone needs a branch
        temp_branch_name = "temp-b-" + commit_id
        source_repo.__branch_create(
            branch_name=temp_branch_name, start_point=commit_id
        )

        # perform the clone from the source repository
        # using the temporary branch
        cloned_repo = GitRepo.clone(
            source=source,
            dest=dest,
            branch=temp_branch_name,
            single_branch=True,
            recurse_submodules=True,
            shallow_submodules=True
        )

        # delete the temporary branch in source repository
        # after the clone operation
        source_repo.__branch_delete(branch_name=temp_branch_name, force=True)

        return cloned_repo
