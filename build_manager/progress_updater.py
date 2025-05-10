import re
import os
import logging
from utils import TaskRunner
from pathlib import Path
from .manager import (
    BuildManager as bm,
    BuildState
)
import json
import time


class BuildProgressUpdater:
    """
    Class for updating the progress of all builds.

    This class ensures that the progress of all  builds is
    updated periodically. It operates in a singleton pattern
    to ensure only one instance manages the updates.
    """

    __singleton = None

    def __init__(self):
        """
        Initialises the BuildProgressUpdater instance.

        This uses the BuildManager singleton, so ensure that BuildManager is
        initialised before creating a BuildProgressUpdater instance.

        Raises:
            RuntimeError: If BuildManager is not initialized or
            if another instance of BuildProgressUpdater has already
            been initialised.
        """
        if not bm.get_singleton():
            raise RuntimeError("BuildManager should be initialised first")

        if BuildProgressUpdater.__singleton:
            raise RuntimeError("BuildProgressUpdater must be a singleton.")

        self.__ensure_status_json()
        # Set up a periodic task to update build progress every 3 seconds
        # TaskRunner will handle scheduling and running the task.
        tasks = (
            (self.__update_build_progress_all, 3),
        )
        self.__runner = TaskRunner(tasks=tasks)
        self.logger = logging.getLogger(__name__)
        BuildProgressUpdater.__singleton = self

    def start(self) -> None:
        """
        Start BuildProgressUpdater.
        """
        self.logger.info("Starting BuildProgressUpdater.")
        self.__runner.start()

    def __calc_running_build_progress_percent(self, build_id: str) -> int:
        """
        Calculate the progress percentage of a running build.

        This method analyses the build log to determine the current completion
        percentage by parsing the build steps from the log file.

        Parameters:
            build_id (str): The unique ID of the build for which progress is
            calculated.

        Returns:
            int: The calculated build progress percentage (0 to 100).

        Raises:
            ValueError: If no build information is found for the provided
            build ID.
        """
        build_info = bm.get_singleton().get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"No build found with ID {build_id}")

        if build_info.progress.state != BuildState.RUNNING:
            raise RuntimeError(
                "This method should only be called for running builds."
            )

        # Construct path to the build's log file
        log_file_path = bm.get_singleton().get_build_log_path(build_id)
        self.logger.debug(f"Opening log file: {log_file_path}")

        try:
            # Read the log content
            with open(log_file_path, encoding='utf-8') as f:
                build_log = f.read()
        except FileNotFoundError:
            self.logger.error(
                f"Log file not found for RUNNING build with ID: {build_id}"
            )
            return build_info.progress.percent

        # Regular expression to extract the build progress steps
        compiled_regex = re.compile(r'(\[\D*(\d+)\D*\/\D*(\d+)\D*\])')
        self.logger.debug(f"Regex pattern: {compiled_regex}")
        all_matches = compiled_regex.findall(build_log)
        self.logger.debug(f"Log matches: {all_matches}")

        # If no matches are found, return a default progress value of 0
        if len(all_matches) < 1:
            return 0

        completed_steps, total_steps = all_matches[-1][1:]
        self.logger.debug(
            f"Completed steps: {completed_steps},"
            f"Total steps: {total_steps}"
        )

        # Handle initial compilation/linking steps (minor weight)
        if int(total_steps) < 20:
            return 1

        # Handle building the OS phase (4% weight)
        if int(total_steps) < 200:
            return (int(completed_steps) * 4 // int(total_steps)) + 1

        # Major build phase (95% weight)
        return (int(completed_steps) * 95 // int(total_steps)) + 5

    def __refresh_running_build_state(self, build_id: str) -> BuildState:
        """
        Refresh the state of a running build.

        This method analyses the build log to determine the build has
        concluded. If yes, it detects the success of a build by finding
        the success message in the log.

        Parameters:
            build_id (str): The unique ID of the build for which progress is
            calculated.

        Returns:
            BuildSate: The current build state based on the log.

        Raises:
            ValueError: If no build information is found for the provided
            build ID.
        """
        build_info = bm.get_singleton().get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"No build found with ID {build_id}")

        if build_info.progress.state != BuildState.RUNNING:
            raise RuntimeError(
                "This method should only be called for running builds."
            )

        # Builder ships the archive post completion
        # This is irrespective of SUCCESS or FAILURE
        if not os.path.exists(
            bm.get_singleton().get_build_archive_path(build_id)
        ):
            return BuildState.RUNNING

        log_file_path = bm.get_singleton().get_build_log_path(build_id)
        try:
            # Read the log content
            with open(log_file_path, encoding='utf-8') as f:
                build_log = f.read()
        except FileNotFoundError:
            self.logger.error(
                f"Log file not found for RUNNING build with ID: {build_id}"
            )
            return BuildState.ERROR

        # Build has finished, check if it succeeded or failed
        flash_summary_pos = build_log.find("Total Flash Used")
        if flash_summary_pos == -1:
            return BuildState.FAILURE
        else:
            return BuildState.SUCCESS

    def __update_build_percent(self, build_id: str) -> None:
        """
        Update the progress percentage of a given build.
        """
        build_info = bm.get_singleton().get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"No build found with ID {build_id}")

        current_state = build_info.progress.state
        current_percent = build_info.progress.percent
        new_percent = current_percent
        self.logger.debug(
            f"Build id: {build_id}, "
            f"Current state: {current_state}, "
            f"Current percentage: {current_percent}, "
        )
        if current_state == BuildState.PENDING:
            # Keep existing percentage
            pass
        elif current_state == BuildState.RUNNING:
            new_percent = self.__calc_running_build_progress_percent(build_id)
        elif current_state == BuildState.SUCCESS:
            new_percent = 100
        elif current_state == BuildState.FAILURE:
            # Keep existing percentage
            pass
        elif current_state == BuildState.ERROR:
            # Keep existing percentage
            pass
        else:
            raise Exception("Unhandled BuildState.")

        self.logger.debug(
            f"Build id: {build_id}, "
            f"New percentage: {new_percent}, "
        )
        if new_percent != current_percent:
            bm.get_singleton().update_build_progress_percent(
                build_id=build_id,
                percent=new_percent
            )

    def __update_build_state(self, build_id: str) -> None:
        """
        Update the state of a given build.
        """
        build_info = bm.get_singleton().get_build_info(build_id=build_id)

        if build_info is None:
            raise ValueError(f"No build found with ID {build_id}")

        current_state = build_info.progress.state
        new_state = current_state
        self.logger.debug(
            f"Build id: {build_id}, "
            f"Current state: {current_state.name}, "
        )

        log_file_path = bm.get_singleton().get_build_log_path(build_id)
        if current_state == BuildState.PENDING:
            # Builder creates log file when it starts
            # running a build
            if os.path.exists(log_file_path):
                new_state = BuildState.RUNNING
        elif current_state == BuildState.RUNNING:
            new_state = self.__refresh_running_build_state(build_id)
        elif current_state == BuildState.SUCCESS:
            # SUCCESS is a conclusive state
            pass
        elif current_state == BuildState.FAILURE:
            # FAILURE is a conclusive state
            pass
        elif current_state == BuildState.ERROR:
            # ERROR is a conclusive state
            pass
        else:
            raise Exception("Unhandled BuildState.")

        self.logger.debug(
            f"Build id: {build_id}, "
            f"New state: {new_state.name}, "
        )
        if current_state != new_state:
            bm.get_singleton().update_build_progress_state(
                build_id=build_id,
                new_state=new_state,
            )

    def __update_build_progress_all(self) -> None:
        """
        Update progress for all builds.

        This method will iterate through all  builds, calculate their
        progress, and update the build manager with the latest progress state
        and percentage.
        """
        for build_id in bm.get_singleton().get_all_build_ids():
            self.__update_build_state(build_id)
            self.__update_build_percent(build_id)

        # Generate status.json after updating build progress.
        self.__generate_status_json()

    def get_status_json_path(self) -> str:
        """
        Path to status.json file.
        """
        return os.path.join(
            bm.get_singleton().get_outdir(),
            'status.json'
        )

    def __ensure_status_json(self) -> None:
        """
        Ensures status.json exists and is a valid JSON file.
        """
        p = Path(self.get_status_json_path())

        if not p.exists():
            # Ensure parent directory exists
            Path.mkdir(p.parent, parents=True, exist_ok=True)

            # write empty json dict
            with open(p, 'w') as f:
                f.write('{}')

    def __generate_status_json(self) -> None:
        """
        Rewrite status.json file.
        """
        all_build_ids_sorted = sorted(
            bm.get_singleton().get_all_build_ids(),
            key=lambda x: bm.get_singleton().get_build_info(x).time_created,
            reverse=True
        )

        self.logger.debug(f"All build ids sorted: {all_build_ids_sorted}")
        # To-do: fix status.json structure,
        # write a list instead of a dict to the file
        builds_dict = {}
        for build_id in all_build_ids_sorted:
            build_info = bm.get_singleton().get_build_info(build_id)
            build_age_min = int(time.time() - build_info.time_created) // 60
            bi_json = {
                'vehicle': build_info.vehicle.capitalize(),
                'board': build_info.board,
                'git_hash_short': build_info.git_hash[:8],
                'features': ', '.join(build_info.selected_features),
                'status': build_info.progress.state.name,
                'progress': build_info.progress.percent,
                'age': "%u:%02u" % ((build_age_min // 60), build_age_min % 60)
            }
            self.logger.debug(f"Build info json: {bi_json}")
            builds_dict[build_id] = bi_json
        self.logger.debug(f"Builds dict: {builds_dict}")

        with open(self.get_status_json_path(), 'w') as f:
            f.write(json.dumps(builds_dict))

    @staticmethod
    def get_singleton() -> "BuildProgressUpdater":
        """
        Get the singleton instance of BuildProgressUpdater.

        Returns:
            BuildProgressUpdater: The singleton instance of this class.
        """
        return BuildProgressUpdater.__singleton
