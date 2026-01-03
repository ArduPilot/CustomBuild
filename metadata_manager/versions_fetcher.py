import logging
import os
import ap_git
import json
import jsonschema
import hashlib
from pathlib import Path
from threading import Lock
from utils import TaskRunner
from .vehicles_manager import VehiclesManager as vehm


class VersionInfo:
    """
    Class to wrap version info properties.
    """
    def __init__(self,
                 remote_info: 'RemoteInfo',
                 commit_ref: str,
                 release_type: str,
                 version_number: str,
                 ap_build_artifacts_url) -> None:
        self.remote_info = remote_info
        self.commit_ref = commit_ref
        self.release_type = release_type
        self.version_number = version_number
        self.ap_build_artifacts_url = ap_build_artifacts_url

        # Generate version_id as remote-sanitized_commit_ref-hash
        # Commit ref is sanitized for URL safety by replacing '/' with '-'
        # Hash is used to ensure unique ID after sanitization of commit_ref,
        # as different commit refs may become identical after replacing '/'
        commit_ref_sanitized = commit_ref.replace('/', '-')
        commit_ref_hash = hashlib.md5(commit_ref.encode()).hexdigest()[:8]
        self.version_id = (
            f"{remote_info.name}-{commit_ref_sanitized}-{commit_ref_hash}"
        )


class RemoteInfo:
    """
    Class to wrap remote info properties.
    """
    def __init__(self,
                 name: str,
                 url: str) -> None:
        self.name = name
        self.url = url

    def to_dict(self):
        return {
            'name': self.name,
            'url': self.url,
        }


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
            RuntimeError: If an instance of this class already exists,
                          enforcing a singleton pattern.
        """
        if vehm.get_singleton() is None:
            raise RuntimeError("VehiclesManager should be initialised first")

        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if VersionsFetcher.__singleton:
            raise RuntimeError("VersionsFetcher must be a singleton.")

        self.logger = logging.getLogger(__name__)

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
        self.logger.info(
            "Starting VersionsFetcher background auto-fetch jobs."
        )
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

    def get_versions_for_vehicle(self, vehicle_id: str) -> list[VersionInfo]:
        """
        Return the list of dictionaries containing the info about the
        versions listed to be built for a particular vehicle.

        Parameters:
            vehicle_id (str): the vehicle ID to fetch versions list for

        Returns:
            list: VersionInfo objects for all versions allowed to be
                  built for the said vehicle.

        """
        if vehicle_id is None:
            raise ValueError("Vehicle ID is a required parameter.")

        vehicle = vehm.get_singleton().get_vehicle_by_id(vehicle_id)
        if vehicle is None:
            raise ValueError(f"Invalid vehicle ID '{vehicle_id}'.")

        vehicle_name = vehicle.name

        versions_list = []
        for remote in self.__get_versions_metadata():
            remote_info = RemoteInfo(
                name=remote.get('name', None),
                url=remote.get('url', None)
            )
            for vehicle in remote['vehicles']:
                if vehicle['name'] != vehicle_name:
                    continue

                for release in vehicle['releases']:
                    versions_list.append(VersionInfo(
                        remote_info=remote_info,
                        commit_ref=release.get('commit_reference', None),
                        release_type=release.get('release_type', None),
                        version_number=release.get('version_number', None),
                        ap_build_artifacts_url=release.get(
                            'ap_build_artifacts_url',
                            None
                        )
                    ))
        return versions_list

    def is_version_listed(self, vehicle_id: str, version_id: str) -> bool:
        """
        Check if a version with given properties mentioned in remotes.json

        Parameters:
            vehicle_id (str): ID of the vehicle for which version is listed
            version_id (str): version ID

        Returns:
            bool: True if the said version is mentioned in remotes.json,
                  False otherwise

        """
        if vehicle_id is None:
            raise ValueError("vehicle_id is a required parameter.")

        if version_id is None:
            raise ValueError("version_id is a required parameter.")

        return version_id in [
            version_info.version_id
            for version_info in
            self.get_versions_for_vehicle(vehicle_id=vehicle_id)
        ]

    def get_version_info(self, vehicle_id: str,
                         version_id: str) -> VersionInfo:
        """
        Find first version matching the given properties in remotes.json

        Parameters:
            vehicle_id (str): ID of the vehicle for which version is listed
            version_id (str): version ID

        Returns:
            VersionInfo: Object for the version matching the properties,
                         None if not found

        """
        return next(
            (
                version
                for version in self.get_versions_for_vehicle(
                    vehicle_id=vehicle_id
                )
                if version.version_id == version_id
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
