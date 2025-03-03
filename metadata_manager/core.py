import logging
import time
import os
import fnmatch
import ap_git
import json
import jsonschema
import redis
import dill
from pathlib import Path
from . import exceptions as ex
from threading import Lock
from utils import TaskRunner

logger = logging.getLogger(__name__)


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
            TooManyInstancesError: If an instance of this class already exists,
                                   enforcing a singleton pattern.
        """
        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if APSourceMetadataFetcher.__singleton:
            raise ex.TooManyInstancesError()

        self.repo = ap_repo
        self.caching_enabled = caching_enabled

        if self.caching_enabled:
            self.__redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=False,
            )
            logger.info(
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
                                 boards: list,
                                 commit_id: str,
                                 ttl_sec: int = 86400) -> None:
        """
        Cache the given list of boards for a particular commit.

        Parameters:
            boards (list): The list of boards.
            commit_id (str): The git sha for the commit.
            ttl_sec (int): Time-to-live (TTL) in seconds after which the
            cached list expires.

        Raises:
            RuntimeError: If the method is called when caching is disabled.
        """
        if not self.caching_enabled:
            raise RuntimeError("Should not be called with caching disabled.")

        key = self.__boards_key(commit_id=commit_id)
        logger.debug(
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
        logger.debug(
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
        logger.debug(
            f"Getting cached build options for commit id {commit_id}, "
            f"Redis Key: {key}"
        )
        value = self.__redis_client.get(key)
        logger.debug(f"Got value {value} at key {key}")
        return dill.loads(value) if value else None

    def __get_boards_at_commit_from_cache(self, commit_id: str) -> list:
        """
        Returns the list of boards for a given commit from cache if exists,
        None otherwise.

        Parameters:
            commit_id (str): The commit id to get boards list for.

        Returns:
            list: A list of boards available at the specified commit.

        Raises:
            RuntimeError: If the method is called when caching is disabled.
        """
        if not self.caching_enabled:
            raise RuntimeError("Should not be called with caching disabled.")

        key = self.__boards_key(commit_id=commit_id)
        logger.debug(
            f"Getting cached boards list for commit id {commit_id}, "
            f"Redis Key: {key}"
        )
        value = self.__redis_client.get(key)
        logger.debug(f"Got value {value} at key {key}")
        return dill.loads(value) if value else None

    def __get_boards_at_commit_from_repo(self, remote: str,
                                         commit_ref: str) -> list:
        """
        Returns the list of boards for a given commit from the git repo.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            list: A list of boards available at the specified commit.
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
        boards.sort()
        return boards

    def __get_build_options_at_commit_from_repo(self, remote: str,
                                                commit_ref: str) -> tuple:
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

    def get_boards_at_commit(self, remote: str,
                             commit_ref: str) -> list:
        """
        Retrieves a list of boards available for building at a
        specified commit and returns the list.
        If caching is enabled, this would first look in the cache for
        the list. In case of a cache miss, it would retrive the list
        by checkout out the git repo and running `board_list.py` and
        cache it.

        Parameters:
            remote (str): The name of the remote repository.
            commit_ref (str): The commit reference to check out.

        Returns:
            list: A list of boards available at the specified commit.
        """
        tstart = time.time()
        if not self.caching_enabled:
            boards = self.__get_boards_at_commit_from_repo(
                remote=remote,
                commit_ref=commit_ref,
            )
            logger.debug(
                f"Took {(time.time() - tstart)} seconds to get boards"
            )
            return boards

        commid_id = self.repo.commit_id_for_remote_ref(
            remote=remote,
            commit_ref=commit_ref,
        )

        logger.debug(f"Fetching boards for commit {commid_id}.")
        cached_boards = self.__get_boards_at_commit_from_cache(
            commit_id=commid_id
        )

        if cached_boards:
            boards = cached_boards
        else:
            logger.debug(
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

        logger.debug(
            f"Took {(time.time() - tstart)} seconds to get boards"
        )
        return boards

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
            logger.debug(
                f"Took {(time.time() - tstart)} seconds to get build options"
            )
            return build_options

        commid_id = self.repo.commit_id_for_remote_ref(
            remote=remote,
            commit_ref=commit_ref,
        )

        logger.debug(f"Fetching build options for commit {commid_id}.")
        cached_build_options = self.__get_build_options_at_commit_from_cache(
            commit_id=commid_id
        )

        if cached_build_options:
            build_options = cached_build_options
        else:
            logger.debug(
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

        logger.debug(
            f"Took {(time.time() - tstart)} seconds to get build options"
        )
        return build_options

    @staticmethod
    def get_singleton():
        return APSourceMetadataFetcher.__singleton


class VersionInfo:
    """
    Class to wrap version info properties inside a single object
    """
    def __init__(self,
                 remote: str,
                 commit_ref: str,
                 release_type: str,
                 version_number: str,
                 ap_build_artifacts_url) -> None:
        self.remote = remote
        self.commit_ref = commit_ref
        self.release_type = release_type
        self.version_number = version_number
        self.ap_build_artifacts_url = ap_build_artifacts_url


class RemoteInfo:
    """
    Class to wrap remote info properties inside a single object
    """
    def __init__(self,
                 name: str,
                 url: str) -> None:
        self.name = name
        self.url = url


class VersionsFetcher:
    """
    Class to fetch the version-to-build metadata from remotes.json
    and provide methods to view the same
    """

    __singleton = None

    def __init__(self, remotes_json_path: str,
                 ap_repo: ap_git.GitRepo):
        """
        Initializes the VersionsFetcher instance
        with a given remotes.json path.

        Parameters:
            remotes_json_path (str): Path to the remotes.json file.
            ap_repo (GitRepo): ArduPilot local git repository. This local
                               repository is shared between the VersionsFetcher
                               and the APSourceMetadataFetcher.

        Raises:
            TooManyInstancesError: If an instance of this class already exists,
                                   enforcing a singleton pattern.
        """
        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if VersionsFetcher.__singleton:
            raise ex.TooManyInstancesError()

        self.__remotes_json_path = remotes_json_path
        self.__ensure_remotes_json()
        self.__access_lock_versions_metadata = Lock()
        self.__versions_metadata = []
        tasks = (
            (self.fetch_ap_releases, 1200),
            (self.fetch_whitelisted_tags, 1200),
        )
        self.__task__runner = TaskRunner(tasks=tasks)
        self.repo = ap_repo
        VersionsFetcher.__singleton = self

    def start(self) -> None:
        """
        Start auto-fetch jobs.
        """
        logger.info("Starting VersionsFetcher background auto-fetch jobs.")
        self.__task__runner.start()

    def get_all_remotes_info(self) -> list[RemoteInfo]:
        """
        Return the list of RemoteInfo objects constructed from the
        information in the remotes.json file

        Returns:
            list: RemoteInfo objects for all remotes mentioned in remotes.json
        """
        return [
            RemoteInfo(
                name=remote.get('name', None),
                url=remote.get('url', None)
            )
            for remote in self.__get_versions_metadata()
        ]

    def get_remote_info(self, remote_name: str) -> RemoteInfo:
        """
        Return the RemoteInfo for the given remote name, None otherwise.

        Returns:
            RemoteInfo: The remote information object.
        """
        return next(
            (
                remote for remote in self.get_all_remotes_info()
                if remote.name == remote_name
            ),
            None
        )

    def get_versions_for_vehicle(self, vehicle_name: str) -> list[VersionInfo]:
        """
        Return the list of dictionaries containing the info about the
        versions listed to be built for a particular vehicle.

        Parameters:
            vehicle_name (str): the vehicle to fetch versions list for

        Returns:
            list: VersionInfo objects for all versions allowed to be
                  built for the said vehicle.

        """
        if vehicle_name is None:
            raise ValueError("Vehicle is a required parameter.")

        versions_list = []
        for remote in self.__get_versions_metadata():
            for vehicle in remote['vehicles']:
                if vehicle['name'] != vehicle_name:
                    continue

                for release in vehicle['releases']:
                    versions_list.append(VersionInfo(
                        remote=remote.get('name', None),
                        commit_ref=release.get('commit_reference', None),
                        release_type=release.get('release_type', None),
                        version_number=release.get('version_number', None),
                        ap_build_artifacts_url=release.get(
                            'ap_build_artifacts_url',
                            None
                        )
                    ))
        return versions_list

    def get_all_vehicles_sorted_uniq(self) -> list[str]:
        """
        Return a sorted list of all vehicles listed in remotes.json structure

        Returns:
            list: Vehicles listed in remotes.json

        """
        vehicles_set = set()
        for remote in self.__get_versions_metadata():
            for vehicle in remote['vehicles']:
                vehicles_set.add(vehicle['name'])
        return sorted(list(vehicles_set))

    def is_version_listed(self, vehicle: str, remote: str,
                          commit_ref: str) -> bool:
        """
        Check if a version with given properties mentioned in remotes.json

        Parameters:
            vehicle (str): vehicle for which version is listed
            remote (str): remote under which the version is listed
            commit_ref(str): commit reference for the version

        Returns:
            bool: True if the said version is mentioned in remotes.json,
                  False otherwise

        """
        if vehicle is None:
            raise ValueError("Vehicle is a required parameter.")

        if remote is None:
            raise ValueError("Remote is a required parameter.")

        if commit_ref is None:
            raise ValueError("Commit reference is a required parameter.")

        return (remote, commit_ref) in [
            (version_info.remote, version_info.commit_ref)
            for version_info in
            self.get_versions_for_vehicle(vehicle_name=vehicle)
        ]

    def get_version_info(self, vehicle: str, remote: str,
                         commit_ref: str) -> VersionInfo:
        """
        Find first version matching the given properties in remotes.json

        Parameters:
            vehicle (str): vehicle for which version is listed
            remote (str): remote under which the version is listed
            commit_ref(str): commit reference for the version

        Returns:
            VersionInfo: Object for the version matching the properties,
                         None if not found

        """
        return next(
            (
                version
                for version in self.get_versions_for_vehicle(
                    vehicle_name=vehicle
                )
                if version.remote == remote and
                version.commit_ref == commit_ref
            ),
            None
        )

    def reload_remotes_json(self) -> None:
        """
        Read remotes.json, validate its structure against the schema
        and cache it in memory
        """
        # load file containing vehicles listed to be built for each
        # remote along with the branches/tags/commits on which the
        # firmware can be built
        remotes_json_schema_path = os.path.join(
            os.path.dirname(__file__),
            'remotes.schema.json'
        )
        with open(self.__remotes_json_path, 'r') as f, \
             open(remotes_json_schema_path, 'r') as s:
            f_content = f.read()

            # Early return if file is empty
            if not f_content:
                return
            versions_metadata = json.loads(f_content)
            schema = json.loads(s.read())
            # validate schema
            jsonschema.validate(instance=versions_metadata, schema=schema)
            self.__set_versions_metadata(versions_metadata=versions_metadata)

        # update git repo with latest remotes list
        self.__sync_remotes_with_ap_repo()

    def __ensure_remotes_json(self) -> None:
        """
        Ensures remotes.json exists and is a valid JSON file.
        """
        p = Path(self.__remotes_json_path)

        if not p.exists():
            # Ensure parent directory exists
            Path.mkdir(p.parent, parents=True, exist_ok=True)

            # write empty json list
            with open(p, 'w') as f:
                f.write('[]')

    def __set_versions_metadata(self, versions_metadata: list) -> None:
        """
        Set versions metadata property with the one passed as parameter
        This requires to acquire the access lock to avoid overwriting the
        object while it is being read
        """
        if versions_metadata is None:
            raise ValueError("versions_metadata is a required parameter. "
                             "Cannot be None.")

        with self.__access_lock_versions_metadata:
            self.__versions_metadata = versions_metadata

    def __get_versions_metadata(self) -> list:
        """
        Read versions metadata property
        This requires to acquire the access lock to avoid reading the list
        while it is being modified

        Returns:
            list: the versions metadata list
        """
        with self.__access_lock_versions_metadata:
            return self.__versions_metadata

    def __sync_remotes_with_ap_repo(self):
        """
        Update the remotes in ArduPilot local repository with the latest
        remotes list.
        """
        remotes = tuple(
            (remote.name, remote.url)
            for remote in self.get_all_remotes_info()
        )
        self.repo.remote_add_bulk(remotes=remotes, force=True)

    def fetch_ap_releases(self) -> None:
        """
        Execute the fetch_releases.py script to update remotes.json
        with Ardupilot's official releases
        """
        from scripts import fetch_releases
        fetch_releases.run(
            base_dir=os.path.join(
                os.path.dirname(self.__remotes_json_path),
                '..',
            ),
            remote_name="ardupilot",
        )
        self.reload_remotes_json()
        return

    def fetch_whitelisted_tags(self) -> None:
        """
        Execute the fetch_whitelisted_tags.py script to update
        remotes.json with tags from whitelisted repos
        """
        from scripts import fetch_whitelisted_tags
        fetch_whitelisted_tags.run(
            base_dir=os.path.join(
                os.path.dirname(self.__remotes_json_path),
                '..',
            )
        )
        self.reload_remotes_json()
        return

    @staticmethod
    def get_singleton():
        return VersionsFetcher.__singleton
