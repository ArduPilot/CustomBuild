import redis
import dill
import fnmatch
import time
import logging
import ap_git
import os


class APSourceMetadataFetcher:
    """
    Class to fetch metadata like available boards, features etc.
    from the AP source code
    """

    __singleton = None

    def __init__(self, ap_repo: ap_git.GitRepo,
                 caching_enabled: bool = False,
                 redis_host: str = 'localhost',
                 redis_port: str = '6379') -> None:
        """
        Initializes the APSourceMetadataFetcher instance
        with a given repository path.

        Parameters:
            ap_repo (GitRepo): ArduPilot local git repository containing
                               the metadata generation scripts.
            caching_enabled (bool): Enable caching metadata for each commit to
            avoid checking out git repo each time.
            redis_host (str): Hostname of the Redis instance to use for caching
            metadata.
            redis_port (int): Port of the Redis instance to use for caching
            metadata

        Raises:
            RuntimeError: If an instance of this class already exists,
                          enforcing a singleton pattern.
        """
        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if APSourceMetadataFetcher.__singleton:
            raise RuntimeError(
                "APSourceMetadataFetcher must be a singleton."
            )

        self.logger = logging.getLogger(__name__)

        self.repo = ap_repo
        self.caching_enabled = caching_enabled

        if self.caching_enabled:
            self.__redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=False,
            )
            self.logger.info(
                f"Redis connection established with {redis_host}:{redis_port}"
            )
            self.__boards_key_prefix = "boards-"
            self.__build_options_key_prefix = "bopts-"

        APSourceMetadataFetcher.__singleton = self

    def __boards_key(self, commit_id: str) -> str:
        """
        Generate the Redis key that stores the boards list for a given commit.

        Parameters:
            commit_id (str): The git sha for the commit.

        Returns:
            str: The Redis key containing the cached board list.
        """
        return self.__boards_key_prefix + f"{commit_id}"

    def __build_options_key(self, commit_id: str) -> str:
        """
        Generate the Redis key that stores the build options list for a given
        commit.

        Parameters:
            commit_id (str): The git sha for the commit.

        Returns:
            str: The Redis key containing the cached build options list.
        """
        return self.__build_options_key_prefix + f"{commit_id}"

    def __cache_boards_at_commit(self,
                                 boards: tuple,
                                 commit_id: str,
                                 ttl_sec: int = 86400) -> None:
        """
        Cache the given tuple of boards for a particular commit.

        Parameters:
            boards (tuple): The tuple of boards (both non-periph and periph).
            commit_id (str): The git sha for the commit.
            ttl_sec (int): Time-to-live (TTL) in seconds after which the
            cached list expires.

        Raises:
            RuntimeError: If the method is called when caching is disabled.
        """
        if not self.caching_enabled:
            raise RuntimeError("Should not be called with caching disabled.")

        key = self.__boards_key(commit_id=commit_id)
        self.logger.debug(
            "Caching boards list "
            f"Redis key: {key}, "
            f"Boards: {boards}, "
            f"TTL: {ttl_sec} sec"
        )
        self.__redis_client.set(
            name=key,
            value=dill.dumps(boards),
            ex=ttl_sec
        )

    def __cache_build_options_at_commit(self,
                                        build_options: list,
                                        commit_id: str,
                                        ttl_sec: int = 86400) -> None:
        """
        Cache the given list of build options for a particular commit.

        Parameters:
            build_options (list): The list of build options.
            commit_id (str): The git sha for the commit.
            ttl_sec (int): Time-to-live (TTL) in seconds after which the
            cached list expires.

        Raises:
            RuntimeError: If the method is called when caching is disabled.
        """
        if not self.caching_enabled:
            raise RuntimeError("Should not be called with caching disabled.")

        key = self.__build_options_key(commit_id=commit_id)
        self.logger.debug(
            "Caching build options "
            f"Redis key: {key}, "
            f"Build Options: {build_options}, "
            f"TTL: {ttl_sec} sec"
        )
        self.__redis_client.set(
            name=key,
            value=dill.dumps(build_options),
            ex=ttl_sec
        )

    def __get_build_options_at_commit_from_cache(self,
                                                 commit_id: str) -> list:
        """
        Retrieves a list of build options available at a specified commit
        from cache if exists, None otherwise.

        Parameters:
            commit_id (str): The commit id to get build options for.

        Returns:
            list: A list of build options available at the specified commit.

        Raises:
            RuntimeError: If the method is called when caching is disabled.
        """
        if not self.caching_enabled:
            raise RuntimeError("Should not be called with caching disabled.")

        key = self.__build_options_key(commit_id=commit_id)
        self.logger.debug(
            f"Getting cached build options for commit id {commit_id}, "
            f"Redis Key: {key}"
        )
        value = self.__redis_client.get(key)
        self.logger.debug(f"Got value {value} at key {key}")
        return dill.loads(value) if value else None

    def __get_boards_at_commit_from_cache(self,
                                          commit_id: str) -> tuple[list, list]:
        """
        Returns the tuple of boards (for non-periph and periph targets,
        in order) for a given commit from cache if exists, None otherwise.

        Parameters:
            commit_id (str): The commit id to get boards list for.

        Returns:
            tuple: A tuple of two lists in order:
                - A list contains boards for NON-'ap_periph' targets.
                - A list contains boards for the 'ap_periph' target.

        Raises:
            RuntimeError: If the method is called when caching is disabled.
        """
        if not self.caching_enabled:
            raise RuntimeError("Should not be called with caching disabled.")

        key = self.__boards_key(commit_id=commit_id)
        self.logger.debug(
            f"Getting cached boards list for commit id {commit_id}, "
            f"Redis Key: {key}"
        )
        value = self.__redis_client.get(key)
        self.logger.debug(f"Got value {value} at key {key}")
        boards = dill.loads(value) if value else None

        if not boards:
            return None

        # Ensure the data retrieved from the cache is correct
        # We should get a tuple containing two lists
        try:
            non_periph_boards, periph_boards = boards
        except ValueError as e:
            self.logger.debug(f"Boards from cache: '{boards}'")
            self.logger.exception(e)
            return None

        return (
            non_periph_boards,
            periph_boards
        )

    def __exclude_boards_matching_patterns(self, boards: list, patterns: list):
        ret = []
        for b in boards:
            excluded = False
            for p in patterns:
                if fnmatch.fnmatch(b.lower(), p.lower()):
                    excluded = True
                    break
            if not excluded:
                ret.append(b)
        return ret

    def __get_boards_at_commit_from_repo(self, remote: str,
                                         commit_ref: str) -> tuple[list, list]:
        """
        Returns the tuple of boards (for both non-periph and periph targets,
        in order) for a given commit from the git repo.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            tuple: A tuple of two lists in order:
                - A list contains boards for NON-'ap_periph' targets.
                - A list contains boards for the 'ap_periph' target.
        """
        with self.repo.get_checkout_lock():
            self.repo.checkout_remote_commit_ref(
                remote=remote,
                commit_ref=commit_ref,
                force=True,
                hard_reset=True,
                clean_working_tree=True
            )
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                name="board_list.py",
                location=os.path.join(
                    self.repo.get_local_path(),
                    'Tools', 'scripts',
                    'board_list.py')
                )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            non_periph_boards = mod.AUTOBUILD_BOARDS
            periph_boards = mod.AP_PERIPH_BOARDS
            self.logger.debug(f"non_periph_boards raw: {non_periph_boards}")
            self.logger.debug(f"periph_boards raw: {periph_boards}")

        non_periph_boards = self.__exclude_boards_matching_patterns(
            boards=non_periph_boards,
            patterns=['fmuv*', 'SITL*'],
        )
        self.logger.debug(f"non_periph_boards filtered: {non_periph_boards}")

        non_periph_boards_sorted = sorted(non_periph_boards)
        periph_boards_sorted = sorted(periph_boards)

        self.logger.debug(
            f"non_periph_boards sorted: {non_periph_boards_sorted}"
        )
        self.logger.debug(f"periph_boards sorted: {periph_boards_sorted}")

        return (
            non_periph_boards_sorted,
            periph_boards_sorted,
        )

    def __get_build_options_at_commit_from_repo(self,
                                                remote: str,
                                                commit_ref: str) -> tuple[
                                                    list,
                                                    list
                                                ]:
        """
        Returns the list of build options for a given commit from the git repo.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            list: A list of build options available at the specified commit.
        """
        with self.repo.get_checkout_lock():
            self.repo.checkout_remote_commit_ref(
                remote=remote,
                commit_ref=commit_ref,
                force=True,
                hard_reset=True,
                clean_working_tree=True
            )
            import importlib.util
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
        return build_options

    def __get_boards_at_commit(self, remote: str,
                               commit_ref: str) -> tuple[list, list]:
        """
        Retrieves lists of boards available for building at a
        specified commit for both NON-'ap_periph' and ap_periph targets
        and returns a tuple containing both lists.
        If caching is enabled, this would first look in the cache for
        the list. In case of a cache miss, it would retrive the list
        by checkout out the git repo and running `board_list.py` and
        cache it.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            tuple: A tuple of two lists in order:
                - A list contains boards for NON-'ap_periph' targets.
                - A list contains boards for the 'ap_periph' target.
        """
        tstart = time.time()
        if not self.caching_enabled:
            boards = self.__get_boards_at_commit_from_repo(
                remote=remote,
                commit_ref=commit_ref,
            )
            self.logger.debug(
                f"Took {(time.time() - tstart)} seconds to get boards"
            )
            return boards

        commid_id = self.repo.commit_id_for_remote_ref(
            remote=remote,
            commit_ref=commit_ref,
        )

        self.logger.debug(f"Fetching boards for commit {commid_id}.")
        cached_boards = self.__get_boards_at_commit_from_cache(
            commit_id=commid_id
        )

        if cached_boards:
            boards = cached_boards
        else:
            self.logger.debug(
                "Cache miss. Fetching boards from repo for "
                f"commit {commid_id}."
            )
            boards = self.__get_boards_at_commit_from_repo(
                remote=remote,
                commit_ref=commid_id,
            )
            self.__cache_boards_at_commit(
                boards=boards,
                commit_id=commid_id,
            )

        self.logger.debug(
            f"Took {(time.time() - tstart)} seconds to get boards"
        )
        return boards

    def get_boards(self, remote: str, commit_ref: str,
                   vehicle: str) -> list:
        """
        Returns a list of boards available for building at a
        specified commit for given vehicle.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.
            vehicle (str): The vehicle to get the boards list for.

        Returns:
            list: A list of boards.
        """
        non_periph_boards, periph_boards = self.__get_boards_at_commit(
            remote=remote,
            commit_ref=commit_ref,
        )

        if vehicle == 'AP_Periph':
            return periph_boards

        return non_periph_boards

    def get_build_options_at_commit(self, remote: str,
                                    commit_ref: str) -> list:
        """
        Retrieves a list of build options available at a specified commit.
        If caching is enabled, this would first look in the cache for
        the list. In case of a cache miss, it would retrive the list
        by checkout out the git repo and running `build_options.py` and
        cache it.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            list: A list of build options available at the specified commit.
        """
        tstart = time.time()

        if not self.caching_enabled:
            build_options = self.__get_build_options_at_commit_from_repo(
                remote=remote,
                commit_ref=commit_ref,
            )
            self.logger.debug(
                f"Took {(time.time() - tstart)} seconds to get build options"
            )
            return build_options

        commid_id = self.repo.commit_id_for_remote_ref(
            remote=remote,
            commit_ref=commit_ref,
        )

        self.logger.debug(f"Fetching build options for commit {commid_id}.")
        cached_build_options = self.__get_build_options_at_commit_from_cache(
            commit_id=commid_id
        )

        if cached_build_options:
            build_options = cached_build_options
        else:
            self.logger.debug(
                "Cache miss. Fetching build options from repo for "
                f"commit {commid_id}."
            )
            build_options = self.__get_build_options_at_commit_from_repo(
                remote=remote,
                commit_ref=commid_id,
            )
            self.__cache_build_options_at_commit(
                build_options=build_options,
                commit_id=commid_id,
            )

        self.logger.debug(
            f"Took {(time.time() - tstart)} seconds to get build options"
        )
        return build_options

    @staticmethod
    def get_singleton():
        return APSourceMetadataFetcher.__singleton
