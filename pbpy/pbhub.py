import subprocess
import os.path
import os
import sys
from zipfile import ZipFile

from pbpy import pblog
from pbpy import pbtools
from pbpy import pbconfig

hub_executable_path = "hub\\hub.exe"
binary_package_name = "Binaries.zip"

def is_pull_binaries_required():
    checksum_json_path = pbconfig.get("checksum_file")
    if not os.path.exists(checksum_json_path):
        return True
    return not pbtools.compare_md5_all(checksum_json_path)

def pull_binaries(version_number: str):
    # Backward compatibility with old PBGet junctions. If it still exists, remove the junction
    if pbtools.is_junction("Binaries") and not pbtools.remove_junction("Binaries"):
        pblog.error("Something went wrong while removing junction for 'Binaries' folder. You should remove that folder manually to solve the problem")
        return False

    # Remove binary package if it exists, hub is not able to overwrite existing files
    if os.path.exists(binary_package_name):
        try:
            os.remove(binary_package_name)
        except Exception as e:
            pblog.error(str(e))
            pblog.error("Exception thrown while trying to remove " + binary_package_name + ". Please remove it manually")
            return False

    try:
        output = str(subprocess.getoutput([hub_executable_path, "release", "download", version_number, binary_package_name]))
        if "Downloading " + binary_package_name in output:
            pass
        elif "Unable to find release with tag name" in output:
            pblog.error("Failed to find release tag " + version_number)
            return False
        elif "The file exists" in output:
            pblog.error("File " + binary_package_name + " was not able to be overwritten. Please remove it manually and run PBSync again")
            return False
        elif not output:
            # hub doesn't print any output if package doesn't exist in release
            pblog.error("Failed to find binary package for release " + version_number)
            return False
        else:
            pblog.error("Unknown error occured while pulling binaries for release " + version_number)
            pblog.error("Command output: " + output)
            return False
    except Exception as e:
        pblog.error(str(e))
        pblog.error("Exception thrown while trying do pull binaries for " + version_number)
        return False

    try:
        checksum_json_path = pbconfig.get("checksum_file")
        if not os.path.exists(checksum_json_path):
            pblog.error("Checksum json file is not found in " + checksum_json_path)
            return False

        if not pbtools.compare_md5_single(binary_package_name, checksum_json_path):
            return False

        with ZipFile(binary_package_name, 'r') as zip_file:
            zip_file.extractall()
            if not pbtools.compare_md5_all(checksum_json_path, True):
                return False

    except Exception as e:
        pblog.error(str(e))
        pblog.error("Exception thrown while trying do extract binary package for " + version_number)
        return False

    return True