import time
import redis
import dill
from enum import Enum
from utils import RateLimiter
import logging
import hashlib
from metadata_manager import RemoteInfo
import os


class BuildState(Enum):
    PENDING = 0
    RUNNING = 1
    SUCCESS = 2
    FAILURE = 3
    ERROR = 4
    TIMED_OUT = 5


class BuildProgress:
    def __init__(
        self,
        state: BuildState,
        percent: int
    ) -> None:
        """
        Initialise the progress property for a build,
        including its state and completion percentage.

        Parameters:
            state (BuildState): The current state of the build.
            percent (int): The completion percentage of the build (0-100).
        """
        self.state = state
        self.percent = percent

    def to_dict(self) -> dict:
        return {
            'state': self.state.name,
            'percent': self.percent,
        }


class BuildInfo:
    def __init__(self,
                 vehicle_id: str,
                 remote_info: RemoteInfo,
                 git_hash: str,
                 board: str,
                 selected_features: set,
                 custom_defines: list[tuple[str, str | None]] = []) -> None:
        """
        Initialize build information object including vehicle,
        remote, git hash, selected features, and progress of the build.
        The progress percentage is initially 0 and the state is PENDING.

        Parameters:
            vehicle_id (str): The vehicle ID associated with the build.
            remote_info (RemoteInfo): The remote repository containing the
            source commit to build on.
            git_hash (str): The git commit hash to build on.
            board (str): Board to build for.
            selected_features (set): Set of features selected for the build.
            custom_defines (list[tuple[str,str|None]]): Custom defines to
            pass to the build.
        """
        self.vehicle_id = vehicle_id
        self.remote_info = remote_info
        self.git_hash = git_hash
        self.board = board
        self.selected_features = selected_features
        self.custom_defines = custom_defines
        self.progress = BuildProgress(
            state=BuildState.PENDING,
            percent=0
        )
        self.time_created = time.time()
        self.time_started = None  # when build state becomes RUNNING

    def to_dict(self) -> dict:
        return {
            'vehicle_id': self.vehicle_id,
            'remote_info': self.remote_info.to_dict(),
            'git_hash': self.git_hash,
            'board': self.board,
            'selected_features': list(self.selected_features),
            'custom_defines': self.custom_defines,
            'progress': self.progress.to_dict(),
            'time_created': self.time_created,
            'time_started': getattr(self, 'time_started', None),
        }


class BuildManager:
    """
    Class to manage the build lifecycle, including build submission,
    announcements, progress updates, and retrieval of build-related
    information.
    """

    __singleton = None

    def __init__(self,
                 outdir: str,
                 redis_host: str = 'localhost',
                 redis_port: int = 6379,
                 redis_task_queue_name: str = 'builds-queue') -> None:
        """
        Initialide the BuildManager instance. This class is responsible
        for interacting with Redis to store build metadata and managing
        build tasks.

        Parameters:
            outdir (str): Path to the directory for storing build artifacts.
            redis_host (str): Hostname of the Redis instance for storing build
            metadata.
            redis_port (int): Port of the Redis instance for storing build
            metadata.
            redis_task_queue_name (str): Redis List name to be used as the
            task queue.

        Raises:
            RuntimeError: If an instance of this class already exists,
            enforcing a singleton pattern.
        """
        if BuildManager.__singleton:
            raise RuntimeError("BuildManager must be a singleton")

        # Initialide Redis client without decoding responses
        # as we use dill for serialization.
        self.__redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False
        )
        self.__task_queue = redis_task_queue_name
        self.__outdir = outdir

        # Initialide an IP-based rate limiter.
        # Allow 10 builds per hour per client
        self.__ip_rate_limiter = RateLimiter(
            redis_host=redis_host,
            redis_port=redis_port,
            time_window_sec=3600,
            allowed_requests=10
        )
        self.__build_entry_prefix = "buildmeta-"
        self.logger = logging.getLogger(__name__)
        self.logger.info(
            "Build Manager initialised with configuration: "
            f"Redis host: {redis_host}, "
            f"Redis port: {redis_port}, "
            f"Redis task queue: {self.__task_queue}, "
            f"Build output directory: {self.__outdir}, "
            f"Build entry prefix: {self.__build_entry_prefix}"
        )
        BuildManager.__singleton = self

    def __del__(self) -> None:
        """
        Gracefully close the Redis connection when the BuildManager instance
        is deleted.
        """
        if self.__redis_client:
            self.logger.debug("Closing Redis connection")
            self.__redis_client.close()

    def __key_from_build_id(self, build_id: str) -> str:
        """
        Generate the Redis key that stores the build information for the given
        build ID.

        Parameters:
            build_id (str): The unique ID for the build.

        Returns:
            str: The Redis key containing the build information.
        """
        return self.__build_entry_prefix + build_id

    def __build_id_from_key(self, key: str) -> str:
        """
        Extract the build ID from the given Redis key.

        Parameters:
            key (str): The Redis key storing build information.

        Returns:
            str: The build ID corresponding to the given Redis key.
        """
        return key[len(self.__build_entry_prefix):]

    def get_outdir(self) -> str:
        """
        Return the directory where build artifacts are stored.

        Returns:
            str: Path to the output directory containing build artifacts.
        """
        return self.__outdir

    def __generate_build_id(self, build_info: BuildInfo) -> str:
        """
        Generate a unique build ID based on the build information and
        current timestamp. The build information is hashed and combined
        with the time to generate the ID.

        Parameters:
            build_info (BuildInfo): The build information object.

        Returns:
            str: The generated build ID (64 characters).
        """
        h = hashlib.md5(
            f"{build_info}-{time.time_ns()}".encode()
        ).hexdigest()
        bid = f"{build_info.vehicle_id}-{build_info.board}-{h}"
        return bid

    def submit_build(self,
                     build_info: BuildInfo,
                     client_ip: str) -> str:
        """
        Submit a new build request, generate a build ID, and queue the
        build for processing.

        Parameters:
            build_info (BuildInfo): The build information.
            client_ip (str): The IP address of the client submitting the
            build request.

        Returns:
            str: The generated build ID for the submitted build.
        """
        self.__ip_rate_limiter.count(client_ip)
        build_id = self.__generate_build_id(build_info)
        self.__insert_build_info(build_id=build_id, build_info=build_info)
        self.__queue_build(build_id=build_id)
        return build_id

    def __queue_build(self,
                      build_id: str) -> None:
        """
        Add the build ID to the Redis task queue for processing.

        Parameters:
            build_id (str): The ID of the build to be queued.
        """
        self.__redis_client.rpush(
            self.__task_queue,
            build_id.encode()
        )

    def get_next_build_id(self, timeout: int = 0) -> str:
        """
        Block until the next build ID is available in the task queue,
        then return it. If timeout is specified and no build is available
        within that time, returns None.

        Parameters:
            timeout (int): Maximum time to wait in seconds. 0 means wait
                          indefinitely.

        Returns:
            str: The ID of the next build to be processed, or None if timeout.
        """
        result = self.__redis_client.blpop(self.__task_queue, timeout=timeout)
        if result is None:
            # Timeout occurred
            return None
        _, build_id_encoded = result
        build_id = build_id_encoded.decode()
        self.logger.debug(f"Next build id: {build_id}")
        return build_id

    def build_exists(self,
                     build_id: str) -> bool:
        """
        Check if a build with the given ID exists in the datastore.

        Parameters:
            build_id (str): The ID of the build to check.

        Returns:
            bool: True if the build exists, False otherwise.
        """
        return self.__redis_client.exists(
            self.__key_from_build_id(build_id=build_id)
        )

    def __insert_build_info(self,
                            build_id: str,
                            build_info: BuildInfo,
                            ttl_sec: int = 86400) -> None:
        """
        Insert the build information into the datastore.

        Parameters:
            build_id (str): The ID of the build.
            build_info (BuildInfo): The build information to store.
            ttl_sec (int): Time-to-live (TTL) in seconds after which the
            build expires.
        """
        if self.build_exists(build_id=build_id):
            raise ValueError(f"Build with id {build_id} already exists")

        key = self.__key_from_build_id(build_id)
        self.logger.debug(
            "Adding build info, "
            f"Redis key: {key}, "
            f"Build Info: {build_info}, "
            f"TTL: {ttl_sec} sec"
        )
        self.__redis_client.set(
            name=key,
            value=dill.dumps(build_info),
            ex=ttl_sec
        )

    def get_build_info(self,
                       build_id: str) -> BuildInfo:
        """
        Retrieve the build information for the given build ID.

        Parameters:
            build_id (str): The ID of the build to retrieve.

        Returns:
            BuildInfo: The build information for the given build ID.
        """
        key = self.__key_from_build_id(build_id=build_id)
        self.logger.debug(
            f"Getting build info for build id {build_id}, Redis Key: {key}"
        )
        value = self.__redis_client.get(key)
        self.logger.debug(f"Got value {value} at key {key}")
        return dill.loads(value) if value else None

    def __update_build_info(self,
                            build_id: str,
                            build_info: BuildInfo) -> None:
        """
        Update the build information for an existing build in datastore.

        Parameters:
            build_id (str): The ID of the build to update.
            build_info (BuildInfo): The new build information to replace
            the existing one.
        """
        key = self.__key_from_build_id(build_id=build_id)
        self.logger.debug(
            "Updating build info, "
            f"Redis key: {key}, "
            f"Build Info: {build_info}, "
            f"TTL: Keeping Same"
        )
        self.__redis_client.set(
            name=key,
            value=dill.dumps(build_info),
            keepttl=True
        )

    def update_build_time_started(self,
                                  build_id: str,
                                  time_started: float) -> None:
        """
        Update the build's time_started timestamp.

        Parameters:
            build_id (str): The ID of the build to update.
            time_started (float): The timestamp when the build started running.
        """
        build_info = self.get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"Build with id {build_id} not found.")

        build_info.time_started = time_started
        self.__update_build_info(
            build_id=build_id,
            build_info=build_info
        )

    def update_build_progress_percent(self,
                                      build_id: str,
                                      percent: int) -> None:
        """
        Update the build's completion percentage.

        Parameters:
            build_id (str): The ID of the build to update.
            percent (int): The new completion percentage (0-100).
        """
        build_info = self.get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"Build with id {build_id} not found.")

        build_info.progress.percent = percent
        self.__update_build_info(
            build_id=build_id,
            build_info=build_info
        )

    def update_build_progress_state(self,
                                    build_id: str,
                                    new_state: BuildState) -> None:
        """
        Update the build's state (e.g., PENDING, RUNNING, SUCCESS, FAILURE).

        Parameters:
            build_id (str): The ID of the build to update.
            new_state (BuildState): The new state to set for the build.
        """
        build_info = self.get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"Build with id {build_id} not found.")

        build_info.progress.state = new_state
        self.__update_build_info(
            build_id=build_id,
            build_info=build_info
        )

    def get_all_build_ids(self) -> list:
        """
        Retrieve the IDs of all builds currently stored in the datastore.

        Returns:
            list: A list of all build IDs.
        """
        keys_encoded = self.__redis_client.keys(
            f"{self.__build_entry_prefix}*"
        )
        keys = [key.decode() for key in keys_encoded]
        self.logger.debug(
            f"Keys with prefix {self.__build_entry_prefix}"
            f": {keys}"
        )
        return [
            self.__build_id_from_key(key)
            for key in keys
        ]

    def get_build_artifacts_dir_path(self, build_id: str) -> str:
        """
        Return the directory at which the build artifacts are stored.

        Parameters:
            build_id (str): The ID of the build.

        Returns:
            str: The build artifacts path.
        """
        return os.path.join(
            self.get_outdir(),
            build_id,
        )

    def get_build_log_path(self, build_id: str) -> str:
        """
        Return the path at which the log for a build is written.

        Parameters:
            build_id (str): The ID of the build.

        Returns:
            str: The path at which the build log is written.
        """
        return os.path.join(
            self.get_build_artifacts_dir_path(build_id),
            'build.log'
        )

    def get_build_archive_path(self, build_id: str) -> str:
        """
        Return the path to the build archive.

        Parameters:
            build_id (str): The ID of the build.

        Returns:
            str: The path to the build archive.
        """
        return os.path.join(
            self.get_build_artifacts_dir_path(build_id),
            f"{build_id}.tar.gz"
        )

    @staticmethod
    def get_singleton() -> "BuildManager":
        """
        Return the singleton instance of the BuildManager class.

        Returns:
            BuildManager: The singleton instance of the BuildManager.
        """
        return BuildManager.__singleton
