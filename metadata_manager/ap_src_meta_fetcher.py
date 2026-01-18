import redis
import dill
import fnmatch
import time
import logging
import ap_git
import os
import re

class BoardMetadata:
        def __init__(self, id: str, name: str, attributes: dict):
            self.id = id
            self.name = name
            self.attributes = attributes

        def to_dict(self) -> dict:
            # keep top-level has_can for backward compatibility
            out = {
                "id": self.id,
                "name": self.name,
                "attributes": self.attributes,
            }
            if "has_can" in self.attributes:
                out["has_can"] = self.attributes["has_can"]
            return out

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
                - A list of board metadata dictionaries for NON-'ap_periph' targets.
                - A list of board metadata dictionaries for the 'ap_periph' target.
            Each dictionary currently exposes:
                - name (str): Board name.
                - has_can (bool): True when the board hwdef declares CAN support.

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

    def __board_has_can(self, hwdef_path: str) -> bool:
        """Return True when the hwdef file advertises CAN support."""
        if not hwdef_path or not os.path.isfile(hwdef_path):
            self.logger.debug(
                "hwdef.dat not found while checking CAN support: %s",
                hwdef_path,
            )
            return False

        try:
            with open(hwdef_path, "r", encoding="utf-8", errors="ignore") as hwdef_file:
                hwdef_contents = hwdef_file.read()
        except OSError as exc:
            self.logger.warning(
                "Failed to read hwdef.dat at %s: %s",
                hwdef_path,
                exc,
            )
            return False

        combined_contents = hwdef_contents

        # If the hwdef uses an include *.inc, read that file as well so
        # CAN keywords defined there are detected (e.g., CubeOrange).
        include_match = re.search(r"^\s*include\s+(.+\.inc)\s*$", hwdef_contents, re.MULTILINE)
        if include_match:
            include_name = include_match.group(1).strip()
            include_path = os.path.join(os.path.dirname(hwdef_path), include_name)
            if os.path.isfile(include_path):
                try:
                    with open(include_path, "r", encoding="utf-8", errors="ignore") as inc_file:
                        combined_contents += "\n" + inc_file.read()
                except OSError as exc:
                    self.logger.warning(
                        "Failed to read included hwdef %s: %s",
                        include_path,
                        exc,
                    )

        return (
            "CAN1" in combined_contents
            or "HAL_NUM_CAN_IFACES" in combined_contents
            or "CAN_P1_DRIVER" in combined_contents
            or "CAN_D1_DRIVER" in combined_contents
        )

    def __get_boards_at_commit_from_repo(self, remote: str,
                                         commit_ref: str) -> tuple[list[dict], list[dict]]:
        """
        Returns the tuple of boards (for both non-periph and periph targets,
        in order) for a given commit from the git repo.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            tuple: A tuple of two lists in order:
                - A list of board metadata dictionaries for NON-'ap_periph' targets.
                - A list of board metadata dictionaries for the 'ap_periph' target.
            Each board dict exposes: id, name, attributes (has_can), and has_can (legacy).
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
            board_list = mod.BoardList()
            hwdef_dir = getattr(board_list, "hwdef_dir", None)
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

        def build_board_metadata(board_names: list[str]) -> list[dict]:
            board_data: list[dict] = []
            for board_name in board_names:
                hwdef_path = None
                if hwdef_dir:
                    candidate_path = os.path.join(hwdef_dir, board_name, "hwdef.dat")
                    if os.path.isfile(candidate_path):
                        hwdef_path = candidate_path
                    else:
                        self.logger.debug(
                            "hwdef.dat not found for board %s at %s",
                            board_name,
                            candidate_path,
                        )

                has_can = self.__board_has_can(hwdef_path) if hwdef_path else False
                board = BoardMetadata(
                    id=board_name,
                    name=board_name,
                    attributes={"has_can": has_can},
                )
                board_data.append(board.to_dict())
            return board_data

        return (
            build_board_metadata(non_periph_boards_sorted),
            build_board_metadata(periph_boards_sorted),
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
                               commit_ref: str) -> tuple[list[dict], list[dict]]:
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
                - A list of board metadata dictionaries for NON-'ap_periph' targets.
                - A list of board metadata dictionaries for the 'ap_periph' target.
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

        if not cached_boards or boards is None:
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
                   vehicle_id: str) -> list:
        """
        Returns a list of boards available for building at a
        specified commit for given vehicle.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.
            vehicle_id (str): The vehicle ID to get the boards list for.

        Returns:
            list: A list of board metadata dictionaries, each containing
            the board name and whether it supports CAN (has_can).
        """
        non_periph_boards, periph_boards = self.__get_boards_at_commit(
            remote=remote,
            commit_ref=commit_ref,
        )

        if vehicle_id == 'ap-periph':
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

    def get_board_defaults_from_fw_server(
        self,
        artifacts_url: str,
        board_id: str,
        vehicle_id: str = None,
    ) -> dict:
        """
        Fetch board defaults from firmware.ardupilot.org features.txt.

        The features.txt file contains lines like:
        - FEATURE_NAME (enabled features)
        - !FEATURE_NAME (disabled features)

        Parameters:
            artifacts_url (str): Base URL for build artifacts for a version.
            board_id (str): Board identifier
            vehicle_id (str): Vehicle identifier
                              (for special handling like Heli)

        Returns:
            dict: Dictionary mapping feature define to state
                  (1 for enabled, 0 for disabled), or None if fetch fails
        """
        import requests

        # Heli builds are stored under a separate folder
        artifacts_subdir = board_id
        if vehicle_id == "Heli":
            artifacts_subdir += "-heli"

        features_txt_url = f"{artifacts_url}/{artifacts_subdir}/features.txt"

        try:
            response = requests.get(features_txt_url, timeout=30)
            response.raise_for_status()

            feature_states = {}
            enabled_count = 0
            disabled_count = 0

            for line in response.text.splitlines():
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Check if feature is disabled (prefixed with !)
                if line.startswith('!'):
                    feature_name = line[1:].strip()
                    if feature_name:
                        feature_states[feature_name] = 0
                        disabled_count += 1
                else:
                    # Enabled feature
                    if line:
                        feature_states[line] = 1
                        enabled_count += 1

            self.logger.info(
                f"Fetched board defaults from firmware server: "
                f"{enabled_count} enabled, "
                f"{disabled_count} disabled"
            )

            return feature_states

        except requests.RequestException as e:
            self.logger.warning(
                f"Failed to fetch board defaults from {features_txt_url}: {e}"
            )
            return None

    @staticmethod
    def get_singleton():
        return APSourceMetadataFetcher.__singleton
