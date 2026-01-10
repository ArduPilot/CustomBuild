from utils import TaskRunner
from .manager import BuildManager as bm
import logging
import shutil
import pathlib


class BuildArtifactsCleaner:
    """
    Class responsible for cleaning up stale build
    artifacts from the build output directory.
    """

    __singleton = None

    def __init__(self) -> None:
        """
        Initialises the BuildArtifactsCleaner instance.
        This class depends on the BuildManager singleton,
        so it ensures that the BuildManager is initialized
        before proceeding.

        Raises:
            RuntimeError: If BuildManager is not initialized or
            if another instance of BuildArtifactsCleaner already
            exists (enforcing the singleton pattern).
        """

        if bm.get_singleton() is None:
            raise RuntimeError("BuildManager should be initialised first")

        if BuildArtifactsCleaner.__singleton:
            raise RuntimeError("BuildArtifactsCleaner must be a singleton")

        # Calls the __run method every 60 seconds.
        tasks = (
            (self.__run, 60),
        )
        # This spins up a new thread
        self.__runner = TaskRunner(tasks=tasks)
        self.logger = logging.getLogger(__name__)
        BuildArtifactsCleaner.__singleton = self

    def start(self) -> None:
        """
        Start BuildArtifactsCleaner.
        """
        self.logger.info("Starting BuildArtifactsCleaner")
        self.__runner.start()

    def stop(self) -> None:
        """
        Stop BuildArtifactsCleaner.
        """
        self.logger.info("Stopping BuildArtifactsCleaner")
        self.__runner.stop()

    def __stale_artifacts_path_list(self) -> list:
        """
        Returns a list of paths to stale build artifacts.

        Returns:
            list: A list of file paths for stale artifacts.
        """
        dir_to_scan = pathlib.Path(bm.get_singleton().get_outdir())
        self.logger.debug(
            f"Scanning directory: {dir_to_scan} for stale artifacts"
        )
        all_build_ids = bm.get_singleton().get_all_build_ids()
        self.logger.debug(f"Retrieved all build IDs: {all_build_ids}")

        dirs_to_keep = [
            pathlib.Path(
                bm.get_singleton().get_build_artifacts_dir_path(build_id)
            )
            for build_id in all_build_ids
        ]

        stale_artifacts = []
        for f in dir_to_scan.iterdir():
            # Check if the current file/dir falls under any directories to keep
            keep_file = any(
                f.is_relative_to(dir)
                for dir in dirs_to_keep
            )
            if not keep_file:
                stale_artifacts.append(str(f))

        self.logger.debug(f"Stale artifacts found: {stale_artifacts}")

        return stale_artifacts

    def __run(self) -> None:
        """
        Iterates over the list of stale build artifacts
        and deletes them from the file system.
        """
        for path in self.__stale_artifacts_path_list():
            self.logger.info(f"Removing stale artifacts at {path}")
            shutil.rmtree(path=path)
        return

    @staticmethod
    def get_singleton() -> "BuildArtifactsCleaner":
        """
        Returns the singleton instance of the BuildArtifactsCleaner class.

        Returns:
            BuildArtifactsCleaner: The singleton instance of the cleaner.
        """
        return BuildArtifactsCleaner.__singleton
