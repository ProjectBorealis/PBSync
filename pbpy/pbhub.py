import os.path
import os
import shutil
import subprocess

from urllib.parse import urlparse
from zipfile import ZipFile

from pbpy import pblog
from pbpy import pbtools
from pbpy import pbconfig
from pbpy import pbgit

hub_executable_path = ".github\\hub\\hub.exe"
binary_package_name = "Binaries.zip"


def get_hub_credentials_env():
    repo_str = pbtools.get_one_line_output([pbgit.get_git_executable(), "remote", "get-url", "origin"])
    repo_url = urlparse(repo_str)

    creds = f"protocol={repo_url.scheme}\n"
    creds += f"host={repo_url.hostname}\n"
    if repo_url.username:
        creds += f"username={repo_url.username}\n"
    creds += "\n"

    proc = subprocess.run([pbgit.get_gcm_executable(), "get"], input=creds, capture_output=True, text=True, shell=True)

    if proc.returncode != 0:
        return 1

    creds = proc.stdout

    pairs = creds.splitlines()
    kv = []
    for pair in pairs:
        if pair:
            kv.append(pair.split("=", 1))
    cred_dict = dict(kv)

    gh_env = {
        "GITHUB_USER": cred_dict.get("username"),
        "GITHUB_PASSWORD": cred_dict.get("password")
    }

    return gh_env


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
            pblog.error(f"Exception thrown while trying to remove {binary_package_name}. Please remove it manually.")
            return -1

    creds = get_hub_credentials_env()

    try:
        output = pbtools.get_combined_output([hub_executable_path, "release", "download", version_number, "-i", binary_package_name], env=creds)
        if f"Downloading {binary_package_name}" in output:
            pass
        elif "Unable to find release with tag name" in output:
            pblog.error(f"Failed to find release tag {version_number}. Please wait and try again later.")
            return -1
        elif "The file exists" in output:
            pblog.error(f"File {binary_package_name} was not able to be overwritten. Please remove it manually and run UpdateProject again.")
            return -1
        elif "did not match any available assets" in output:
            pblog.error("Binaries for release {version_number} are not pushed into GitHub yet. Please wait and try again later.")
            return -1
        elif not output:
            # hub doesn't print any output if package doesn't exist in release
            pblog.error(f"Failed to find binary package for release {version_number}")
            return 1
        else:
            pblog.error(f"Unknown error occurred while pulling binaries for release {version_number}")
            pblog.error(f"Command output was: {output}")
            return 1
    except Exception as e:
        pblog.exception(str(e))
        pblog.error(
            f"Exception thrown while trying do pull binaries for {version_number}")
        return 1

    # Temp fix for Binaries folder with unnecessary content
    if os.path.isdir("Binaries"):
        try:
            shutil.rmtree("Binaries")
        except Exception as e:
            pblog.exception(str(e))
            pblog.error("Exception thrown while trying do clean Binaries folder")
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
        pblog.error(f"Exception thrown while trying do extract binary package for {version_number}")
        return 1

    return 0


def push_package(version_number, file_name):
    if not os.path.exists(file_name):
        pblog.error(f"Provided file {file_name} doesn't exist")
        return False

    creds = get_hub_credentials_env()

    try:
        output = pbtools.get_combined_output([hub_executable_path, "release", "edit", version_number, "-m", "", "-a", file_name], env=creds)
        if "Attaching 1 asset..." in output:
            return True
        else:
            pblog.error(output)
    except Exception as e:
        pblog.exception(str(e))
    pblog.error(f"Error occurred while attaching {file_name} into release {version_number}")
    return False
