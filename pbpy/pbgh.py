import os.path
import os
import shutil
import subprocess

from zipfile import ZipFile
from functools import lru_cache

from pbpy import pblog
from pbpy import pbtools
from pbpy import pbconfig
from pbpy import pbgit
from pbpy import pbunreal

gh_executable_path = ".github\\gh\\gh.exe"
chglog_executable_path = ".github\\gh\\git-chglog.exe"
chglog_config_path = ".github\\chglog.yml"
release_file = "RELEASE_MSG"
binary_package_name = "Binaries.zip"


@lru_cache()
def get_token_env():
    _, token = pbgit.get_credentials()

    if token:
        return {
            "GITHUB_TOKEN": token
        }
    else:
        pbtools.error_state(f"Credential retrieval failed. Please get help from {pbconfig.get('support_channel')}")


def download_release_file(version, pattern=None, directory=None, repo=None):
    if not os.path.isfile(gh_executable_path):
        pblog.error(f"GH CLI executable not found at {gh_executable_path}")
        return 1

    args = [gh_executable_path, "release", "download", version]

    if directory:
        args.extend(["-D", directory])
    else:
        directory = "."

    def try_remove(path):
        path = os.path.join(directory, path)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                pblog.exception(str(e))
                pblog.error(f"Exception thrown while removing {path}. Please remove it manually.")
                return -1
        return 0

    def check_wildcard(path):
        if "*" in file:
            return False
        return True

    if pattern:
        if not isinstance(pattern, list):
            pattern = [pattern]
        for file in pattern:
            if check_wildcard(file):
                res = try_remove(file)
                if res != 0:
                    return res
            args.extend(["-p", file])
    else:
        pattern = "*"

    if repo:
        args.extend(["-R", repo])

    creds = get_token_env()

    try:
        proc = pbtools.run_with_combined_output(args, env=creds)
        output = proc.stdout
        if proc.returncode == 0:
            pass
        elif pbtools.it_has_any(output, "release not found", "no assets"):
            pblog.error(f"Release {version} not found. Please wait and try again later.")
            return -1
        elif "The file exists" in output:
            pblog.error(f"File {directory}/{pattern} was not able to be overwritten. Please remove it manually and run UpdateProject again.")
            return -1
        else:
            pblog.error(f"Unknown error occurred while pulling release file {pattern} for release {version}")
            pblog.error(f"Command output was: {output}")
            return 1
    except Exception as e:
        pblog.exception(str(e))
        pblog.error(
            f"Exception thrown while pulling release file {file} for {version}")
        return 1

    return 0


def is_pull_binaries_required():
    if not os.path.isfile(gh_executable_path):
        return False
    checksum_json_path = pbconfig.get("checksum_file")
    if not os.path.exists(checksum_json_path):
        return False
    return not pbtools.compare_hash_all(checksum_json_path)


def pull_binaries(version_number: str, pass_checksum=False):
    if pass_checksum:
        checksum_json_path = None
    else:
        checksum_json_path = pbconfig.get("checksum_file")
        if not os.path.exists(checksum_json_path):
            pblog.error(f"Checksum json file not found at {checksum_json_path}")
            return 1

    if not pbtools.compare_hash_single(binary_package_name, checksum_json_path):
        if not os.path.isfile(gh_executable_path):
            pblog.error(f"GH CLI executable not found at {gh_executable_path}")
            return 1

        # Remove binary package if it exists, gh is not able to overwrite existing files
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

        if not pbtools.compare_hash_single(binary_package_name, checksum_json_path):
            return 1

    pbunreal.ensure_ue_closed()

    # Temp fix for Binaries folder with unnecessary content
    if os.path.isdir("Binaries"):
        try:
            shutil.rmtree("Binaries")
        except Exception as e:
            pblog.exception(str(e))
            pblog.error("Exception thrown while cleaning Binaries folder")
            return 1
    try:
        with ZipFile(binary_package_name) as zip_file:
            zip_file.extractall()
            if pass_checksum:
                return 0
            elif not pbtools.compare_hash_all(checksum_json_path, True):
                return 1

    except Exception as e:
        pblog.exception(str(e))
        pblog.error(f"Exception thrown while extracting binary package for {version_number}")
        return 1

    return 0


def generate_release():
    version = pbunreal.get_latest_project_version()
    target_branch = pbconfig.get("expected_branch_name")
    proc = pbtools.run_with_combined_output([pbgit.get_git_executable(), "rev-parse", version, "--"])
    if proc.returncode == 0:
        pblog.error("Tag already exists. Not creating a release.")
        pblog.info("Please use --autoversion {release,update,hotfix} if you'd like to make a new version.")
        return
    proc =  pbtools.run_with_combined_output([pbgit.get_git_executable(), "tag", version])
    pblog.info(proc.stdout)
    proc =  pbtools.run_with_combined_output([pbgit.get_git_executable(), "push", "origin", version])
    pblog.info(proc.stdout)
    proc = pbtools.run_with_combined_output([
        chglog_executable_path,
        "-c", chglog_config_path,
        "-o", release_file,
        version
    ])
    if proc.returncode != 0:
        os.remove(release_file)
        pbtools.error_state(proc.stdout)
    else:
        pblog.info(proc.stdout)
    
    if pbconfig.get("is_ci"):
        creds = None
    else:
        creds = get_token_env()
    
    proc = pbtools.run_with_combined_output([
        gh_executable_path,
        "release",
        "create", version, binary_package_name,
        "-F", release_file,
        "--target", target_branch,
        "-t", version
    ], env=creds)
    if proc.returncode != 0:
        os.remove(release_file)
        pbtools.error_state(proc.stdout)
    else:
        pblog.info(proc.stdout)
    os.remove(release_file)
