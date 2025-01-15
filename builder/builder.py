import ap_git
from build_manager import (
    BuildManager as bm,
)
import subprocess
import os
import shutil
import logging
import tarfile
from metadata_manager import (
    APSourceMetadataFetcher as apfetch,
    RemoteInfo,
)
from pathlib import Path


class Builder:
    """
    Processes build requests, perform builds and ship build artifacts
    to the destination directory shared by BuildManager.
    """

    def __init__(self, workdir: str, source_repo: ap_git.GitRepo) -> None:
        """
        Initialises the Builder class.

        Parameters:
            workdir (str): Workspace for the builder.
            source_repo (ap_git.GitRepo): Ardupilot repository to be used for
                                          retrieving source for doing builds.

        Raises:
            RuntimeError: If BuildManager or APSourceMetadataFetcher is not
            initialised.
        """
        if bm.get_singleton() is None:
            raise RuntimeError(
                "BuildManager should be initialized first."
            )
        if apfetch.get_singleton() is None:
            raise RuntimeError(
                "APSourceMetadataFetcher should be initialised first."
            )

        self.__workdir_parent = workdir
        self.__master_repo = source_repo
        self.logger = logging.getLogger(__name__)

    def __log_build_info(self, build_id: str) -> None:
        """
        Logs the build information to the build log.

        Parameters:
            build_id (str): Unique identifier for the build.
        """
        build_info = bm.get_singleton().get_build_info(build_id)
        logpath = bm.get_singleton().get_build_log_path(build_id)
        with open(logpath, "a") as build_log:
            build_log.write(f"Vehicle: {build_info.vehicle}\n"
                            f"Board: {build_info.board}\n"
                            f"Remote URL: {build_info.remote_info.url}\n"
                            f"git-sha: {build_info.git_hash}\n"
                            "---\n"
                            "Selected Features:\n")
            for d in build_info.selected_features:
                build_log.write(f"{d}\n")
            build_log.write("---\n")

    def __generate_extrahwdef(self, build_id: str) -> None:
        """
        Generates the extra hardware definition file (`extra_hwdef.dat`) for
        the build.

        Parameters:
            build_id (str): Unique identifier for the build.

        Raises:
            RuntimeError: If the parent directory for putting `extra_hwdef.dat`
            does not exist.
        """
        # Log to build log
        logpath = bm.get_singleton().get_build_log_path(build_id)
        with open(logpath, "a") as build_log:
            build_log.write("Generating extrahwdef file...\n")

        path = self.__get_path_to_extra_hwdef(build_id)
        self.logger.debug(
            f"Path to extra_hwdef for build id {build_id}: {path}"
        )
        if not os.path.exists(os.path.dirname(path)):
            raise RuntimeError(
                f"Create parent directory '{os.path.dirname(path)}' "
                "before writing extra_hwdef.dat"
            )

        build_info = bm.get_singleton().get_build_info(build_id)
        selected_features = build_info.selected_features
        self.logger.debug(
            f"Selected features for {build_id}: {selected_features}"
        )
        all_features = apfetch.get_singleton().get_build_options_at_commit(
            remote=build_info.remote_info.name,
            commit_ref=build_info.git_hash,
        )
        all_defines = {
            feature.define
            for feature in all_features
        }
        enabled_defines = selected_features.intersection(all_defines)
        disabled_defines = all_defines.difference(enabled_defines)
        self.logger.info(f"Enabled defines for {build_id}: {enabled_defines}")
        self.logger.info(f"Disabled defines for {build_id}: {enabled_defines}")

        with open(self.__get_path_to_extra_hwdef(build_id), "w") as f:
            # Undefine all defines at the beginning
            for define in all_defines:
                f.write(f"undef {define}\n")
            # Enable selected defines
            for define in enabled_defines:
                f.write(f"define {define} 1\n")
            # Disable the remaining defines
            for define in disabled_defines:
                f.write(f"define {define} 0\n")

    def __ensure_remote_added(self, remote_info: RemoteInfo) -> None:
        """
        Ensures that the remote repository is correctly added to the
        master repository.

        Parameters:
            remote_info (RemoteInfo): Information about the remote repository.
        """
        try:
            self.__master_repo.remote_add(
                remote=remote_info.name,
                url=remote_info.url,
            )
            self.logger.info(
                f"Added remote {remote_info.name} to master repo."
            )
        except ap_git.DuplicateRemoteError:
            self.logger.debug(
                f"Remote {remote_info.name} already exists."
                f"Setting URL to {remote_info.url}."
            )
            # Update the URL if the remote already exists
            self.__master_repo.remote_set_url(
                remote=remote_info.name,
                url=remote_info.url,
            )
            self.logger.info(
                f"Updated remote url to {remote_info.url}"
                f"for remote {remote_info.name}"
            )

    def __provision_build_source(self, build_id: str) -> None:
        """
        Provisions the source code for a specific build.

        Parameters:
            build_id (str): Unique identifier for the build.
        """
        # Log to build log
        logpath = bm.get_singleton().get_build_log_path(build_id)
        with open(logpath, "a") as build_log:
            build_log.write("Cloning build source...\n")

        build_info = bm.get_singleton().get_build_info(build_id)
        logging.info(
            f"Ensuring {build_info.remote_info.name} is added to master repo."
        )
        self.__ensure_remote_added(build_info.remote_info)

        logging.info(f"Cloning build source for {build_id} from master repo.")

        ap_git.GitRepo.shallow_clone_at_commit_from_local(
            source=self.__master_repo.get_local_path(),
            remote=build_info.remote_info.name,
            commit_ref=build_info.git_hash,
            dest=self.__get_path_to_build_src(build_id),
        )

    def __create_build_artifacts_dir(self, build_id: str) -> None:
        """
        Creates the output directory to store build artifacts.

        Parameters:
            build_id (str): Unique identifier for the build.
        """
        p = Path(bm.get_singleton().get_build_artifacts_dir_path(build_id))
        self.logger.info(f"Creating directory at {p}.")
        try:
            Path.mkdir(p, parents=True)
        except FileExistsError:
            shutil.rmtree(p)
            Path.mkdir(p)

    def __create_build_workdir(self, build_id: str) -> None:
        """
        Creates the working directory for the build.

        Parameters:
            build_id (str): Unique identifier for the build.
        """
        p = Path(self.__get_path_to_build_dir(build_id))
        self.logger.info(f"Creating directory at {p}.")
        try:
            Path.mkdir(p, parents=True)
        except FileExistsError:
            shutil.rmtree(p)
            Path.mkdir(p)

    def __generate_archive(self, build_id: str) -> None:
        """
        Placeholder for generating the zipped build artifact.

        Parameters:
            build_id (str): Unique identifier for the build.
        """
        build_info = bm.get_singleton().get_build_info(build_id)
        archive_path = bm.get_singleton().get_build_archive_path(build_id)

        files_to_include = []

        # include binaries
        bin_path = os.path.join(
            self.__get_path_to_build_dir(build_id),
            build_info.board,
            "bin"
        )
        bin_list = os.listdir(bin_path)
        self.logger.debug(f"bin_path: {bin_path}")
        self.logger.debug(f"bin_list: {bin_list}")
        for file in bin_list:
            file_path_abs = os.path.abspath(
                os.path.join(bin_path, file)
            )
            files_to_include.append(file_path_abs)

        # include log
        log_path_abs = os.path.abspath(
            bm.get_singleton().get_build_log_path(build_id)
        )
        files_to_include.append(log_path_abs)

        # include extra_hwdef.dat
        extra_hwdef_path_abs = os.path.abspath(
            self.__get_path_to_extra_hwdef(build_id)
        )
        files_to_include.append(extra_hwdef_path_abs)

        # create archive
        with tarfile.open(archive_path, "w:gz") as tar:
            for file in files_to_include:
                arcname = f"{build_id}/{os.path.basename(file)}"
                self.logger.debug(f"Added {file} as {arcname}")
                tar.add(file, arcname=arcname)
        self.logger.info(f"Generated {archive_path}.")

    def __clean_up_build_workdir(self, build_id: str) -> None:
        shutil.rmtree(self.__get_path_to_build_dir(build_id))

    def __process_build(self, build_id: str) -> None:
        """
        Processes a new build by preparing source code and extra_hwdef file
        and running the build finally.

        Parameters:
            build_id (str): Unique identifier for the build.
        """
        self.__create_build_workdir(build_id)
        self.__create_build_artifacts_dir(build_id)
        self.__log_build_info(build_id)
        self.__provision_build_source(build_id)
        self.__generate_extrahwdef(build_id)
        self.__build(build_id)
        self.__generate_archive(build_id)
        self.__clean_up_build_workdir(build_id)

    def __get_path_to_build_dir(self, build_id: str) -> str:
        """
        Returns the path to the temporary workspace for a build.
        This directory contains the source code and extra_hwdef.dat file.

        Parameters:
            build_id (str): Unique identifier for the build.

        Returns:
            str: Path to the build directory.
        """
        return os.path.join(self.__workdir_parent, build_id)

    def __get_path_to_extra_hwdef(self, build_id: str) -> str:
        """
        Returns the path to the extra_hwdef definition file for a build.

        Parameters:
            build_id (str): Unique identifier for the build.

        Returns:
            str: Path to the extra hardware definition file.
        """
        return os.path.join(
            self.__get_path_to_build_dir(build_id),
            "extra_hwdef.dat",
        )

    def __get_path_to_build_src(self, build_id: str) -> str:
        """
        Returns the path to the source code for a build.

        Parameters:
            build_id (str): Unique identifier for the build.

        Returns:
            str: Path to the build source directory.
        """
        return os.path.join(
            self.__get_path_to_build_dir(build_id),
            "build_src"
        )

    def __build(self, build_id: str) -> None:
        """
        Executes the actual build process for a build.
        This should be called after preparing build source code and
        extra_hwdef file.

        Parameters:
            build_id (str): Unique identifier for the build.

        Raises:
            RuntimeError: If source directory or extra hardware definition
            file does not exist.
        """
        if not os.path.exists(self.__get_path_to_build_dir(build_id)):
            raise RuntimeError("Creating build before building.")
        if not os.path.exists(self.__get_path_to_build_src(build_id)):
            raise RuntimeError("Cannot build without source code.")
        if not os.path.exists(self.__get_path_to_extra_hwdef(build_id)):
            raise RuntimeError("Cannot build without extra_hwdef.dat file.")

        build_info = bm.get_singleton().get_build_info(build_id)
        source_repo = ap_git.GitRepo(self.__get_path_to_build_src(build_id))

        # Checkout the specific commit and ensure submodules are updated
        source_repo.checkout_remote_commit_ref(
            remote=build_info.remote_info.name,
            commit_ref=build_info.git_hash,
            force=True,
            hard_reset=True,
            clean_working_tree=True,
        )
        source_repo.submodule_update(init=True, recursive=True, force=True)

        logpath = bm.get_singleton().get_build_log_path(build_id)
        with open(logpath, "a") as build_log:
            # Log initial configuration
            build_log.write(
                "Setting vehicle to: "
                f"{build_info.vehicle.capitalize()}\n"
            )
            build_log.flush()

            # Run the build steps
            self.logger.info("Running waf configure")
            build_log.write("Running waf configure\n")
            build_log.flush()
            subprocess.run(
                [
                    "python3",
                    "./waf",
                    "configure",
                    "--board",
                    build_info.board,
                    "--out",
                    self.__get_path_to_build_dir(build_id),
                    "--extra-hwdef",
                    self.__get_path_to_extra_hwdef(build_id),
                ],
                cwd=self.__get_path_to_build_src(build_id),
                stdout=build_log,
                stderr=build_log,
                shell=False,
            )

            self.logger.info("Running clean")
            build_log.write("Running clean\n")
            build_log.flush()
            subprocess.run(
                ["python3", "./waf", "clean"],
                cwd=self.__get_path_to_build_src(build_id),
                stdout=build_log,
                stderr=build_log,
                shell=False,
            )

            self.logger.info("Running build")
            build_log.write("Running build\n")
            build_log.flush()
            subprocess.run(
                ["python3", "./waf", build_info.vehicle.lower()],
                cwd=self.__get_path_to_build_src(build_id),
                stdout=build_log,
                stderr=build_log,
                shell=False,
            )
            build_log.write("done build\n")
            build_log.flush()

    def run(self) -> None:
        """
        Continuously processes builds in the queue until termination.
        """
        while True:
            build_to_process = bm.get_singleton().get_next_build_id()
            self.__process_build(build_id=build_to_process)
