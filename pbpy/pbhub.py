import subprocess
import os.path
import os
import shutil
from zipfile import ZipFile
from pathlib import Path

from pbpy import pblog
from pbpy import pbtools
from pbpy import pbconfig

hub_executable_path = "hub\\hub.exe"
hub_config_path = f"{str(Path.home())}\\.config\\hub"
binary_package_name = "Binaries.zip"


def is_pull_binaries_required():
    if not os.path.isfile(hub_executable_path):
        return True
    checksum_json_path = pbconfig.get("checksum_file")
    if not os.path.exists(checksum_json_path):
        return True
    return not pbtools.compare_md5_all(checksum_json_path)


def pull_binaries(version_number: str, pass_checksum=False):
    if not os.path.isfile(hub_executable_path):
        pblog.error(f"Hub executable is not found at {hub_executable_path}")
        return False

    # Backward compatibility with old PBGet junctions. If it still exists, remove the junction
    if pbtools.is_junction("Binaries") and not pbtools.remove_junction("Binaries"):
        pblog.error(
            "Something went wrong while removing junction for 'Binaries' folder. You should remove that folder manually to solve the problem")
        return False

    # Remove binary package if it exists, hub is not able to overwrite existing files
    if os.path.exists(binary_package_name):
        try:
            os.remove(binary_package_name)
        except Exception as e:
            pblog.exception(str(e))
            pblog.error(f"Exception thrown while trying to remove {binary_package_name}. Please remove it manually")
            return False

    if not os.path.isfile(hub_config_path):
        # If user didn't login with hub yet, do it now for once
        output = pbtools.run_with_combined_output([hub_executable_path, "release", "-L", "1"]).stdout
        pblog.info(output)
        if not os.path.isfile(hub_config_path):
            pblog.error(
                "Failed to login into hub with git credentials. Please check if your provided credentials are valid.")
            return False
        else:
            pblog.info("Login to hub API was successful")

    try:
        output = pbtools.get_combined_output([hub_executable_path, "release", "download", version_number, "-i", binary_package_name])
        if f"Downloading {binary_package_name}" in output:
            pass
        elif "Unable to find release with tag name" in output:
            pblog.error(f"Failed to find release tag {version_number}")
            return False
        elif "The file exists" in output:
            pblog.error(f"File {binary_package_name} was not able to be overwritten. Please remove it manually and run PBSync again")
            return False
        elif "did not match any available assets" in output:
            pblog.error("Binaries for release {version_number} are not pushed into GitHub yet")
            return False
        elif not output:
            # hub doesn't print any output if package doesn't exist in release
            pblog.error(f"Failed to find binary package for release {version_number}")
            return False
        else:
            pblog.error(
                f"Unknown error occurred while pulling binaries for release {version_number}")
            pblog.error(f"Command output was: {output}")
            return False
    except Exception as e:
        pblog.exception(str(e))
        pblog.error(
            f"Exception thrown while trying do pull binaries for {version_number}")
        return False

    # Temp fix for Binaries folder with unnecessary content
    if os.path.isdir("Binaries"):
        try:
            shutil.rmtree("Binaries")
        except Exception as e:
            pblog.exception(str(e))
            pblog.error(
                "Exception thrown while trying do clean Binaries folder")
            return False
    try:
        if pass_checksum:
            checksum_json_path = None
        else:
            checksum_json_path = pbconfig.get("checksum_file")
            if not os.path.exists(checksum_json_path):
                pblog.error(
                    f"Checksum json file is not found at {checksum_json_path}")
                return False

            if not pbtools.compare_md5_single(binary_package_name, checksum_json_path):
                return False

        with ZipFile(binary_package_name) as zip_file:
            zip_file.extractall()
            if pass_checksum:
                return True
            elif not pbtools.compare_md5_all(checksum_json_path, True):
                return False

    except Exception as e:
        pblog.exception(str(e))
        pblog.error(
            f"Exception thrown while trying do extract binary package for {version_number}")
        return False

    return True


def push_package(version_number, file_name):
    if not os.path.exists(file_name):
        pblog.error(f"Provided file {file_name} doesn't exist")
        return False

    try:
        output = pbtools.get_combined_output([hub_executable_path, "release", "edit", version_number, "-ma", file_name])
        if "Attaching 1 asset..." in output:
            return True
        else:
            pblog.error(output)
    except Exception as e:
        pblog.exception(str(e))
    pblog.error(f"Error occurred while attaching {file_name} into release {version_number}")
    return False
