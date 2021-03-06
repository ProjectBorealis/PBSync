import os.path
import os
import shutil
import subprocess

from zipfile import ZipFile

from pbpy import pblog
from pbpy import pbtools
from pbpy import pbconfig
from pbpy import pbgit
from pbpy import pbunreal

gh_executable_path = ".github\\gh\\gh.exe"
binary_package_name = "Binaries.zip"


def get_token_env():
    _, token = pbgit.get_credentials()

    if token:
        return {
            "GITHUB_TOKEN": token
        }
    else:
        pbtools.error_state("Credential retrieval failed. Please get help from #tech-support")


def is_pull_binaries_required():
    if not os.path.isfile(gh_executable_path):
        return True
    checksum_json_path = pbconfig.get("checksum_file")
    if not os.path.exists(checksum_json_path):
        return True
    return not pbtools.compare_md5_all(checksum_json_path)


def pull_binaries(version_number: str, pass_checksum=False):
    if not os.path.isfile(gh_executable_path):
        pblog.error(f"GH CLI executable not found at {gh_executable_path}")
        return 1

    # Backward compatibility with old PBGet junctions. If it still exists, remove the junction
    if pbtools.is_junction("Binaries") and not pbtools.remove_junction("Binaries"):
        pblog.error("Something went wrong while removing junction for 'Binaries' folder. You should remove that folder manually to solve the problem")
        return -1

    # Remove binary package if it exists, hub is not able to overwrite existing files
    if os.path.exists(binary_package_name):
        try:
            os.remove(binary_package_name)
        except Exception as e:
            pblog.exception(str(e))
            pblog.error(f"Exception thrown while removing {binary_package_name}. Please remove it manually.")
            return -1

    creds = get_token_env()

    try:
        proc = pbtools.run_with_combined_output([gh_executable_path, "release", "download", version_number, "-p", binary_package_name], env=creds)
        output = proc.stdout
        if proc.returncode == 0:
            pass
        elif pbtools.it_has_any(output, "release not found", "no assets"):
            pblog.error(f"Release {version_number} not found. Please wait and try again later.")
            return -1
        elif "The file exists" in output:
            pblog.error(f"File {binary_package_name} was not able to be overwritten. Please remove it manually and run UpdateProject again.")
            return -1
        else:
            pblog.error(f"Unknown error occurred while pulling binaries for release {version_number}")
            pblog.error(f"Command output was: {output}")
            return 1
    except Exception as e:
        pblog.exception(str(e))
        pblog.error(
            f"Exception thrown while pulling binaries for {version_number}")
        return 1

    pbunreal.ensure_ue4_closed()

    # Temp fix for Binaries folder with unnecessary content
    if os.path.isdir("Binaries"):
        try:
            shutil.rmtree("Binaries")
        except Exception as e:
            pblog.exception(str(e))
            pblog.error("Exception thrown while cleaning Binaries folder")
            return 1
    try:
        if pass_checksum:
            checksum_json_path = None
        else:
            checksum_json_path = pbconfig.get("checksum_file")
            if not os.path.exists(checksum_json_path):
                pblog.error(f"Checksum json file is not found at {checksum_json_path}")
                return 1

            if not pbtools.compare_md5_single(binary_package_name, checksum_json_path):
                return 1

        with ZipFile(binary_package_name) as zip_file:
            zip_file.extractall()
            if pass_checksum:
                return 0
            elif not pbtools.compare_md5_all(checksum_json_path, True):
                return 1

    except Exception as e:
        pblog.exception(str(e))
        pblog.error(f"Exception thrown while extracting binary package for {version_number}")
        return 1

    return 0
