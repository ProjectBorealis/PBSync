import os
import shutil
import json
import stat
import pathlib
import multiprocessing
import itertools
import pathlib

from urllib.parse import urlparse
from functools import lru_cache

from pbpy import pblog
from pbpy import pbconfig
from pbpy import pbtools

missing_version = "not installed"


@lru_cache()
def get_current_branch_name():
    return pbtools.get_one_line_output([get_git_executable(), "branch", "--show-current"])


def compare_with_current_branch_name(compared_branch):
    return get_current_branch_name() == compared_branch


@lru_cache
def is_on_expected_branch():
    binaries_mode = pbconfig.get_user("project", "binaries", "on")
    if binaries_mode == "force":
        return True
    elif binaries_mode == "local":
        return False
    return compare_with_current_branch_name(pbconfig.get("expected_branch_name"))


@lru_cache()
def get_git_executable():
    return pbconfig.get_user("paths", "git", "git")


@lru_cache()
def get_lfs_executable():
    return pbconfig.get_user("paths", "git-lfs", "git-lfs")


@lru_cache()
def get_gcm_executable():
    gcm_exec = pbtools.get_one_line_output([get_git_executable(), "config", "--get", "credential.helper"]).replace("\\", "")
    # no helper installed
    if not gcm_exec:
        return None
    # helper installed, but not GCM Core
    if "git-credential-manager-core" not in gcm_exec:
        return f"diff.{gcm_exec}"
    return gcm_exec


def get_git_version():
    installed_version_split = pbtools.get_one_line_output([get_git_executable(), "--version"]).split(" ")

    list_len = len(installed_version_split)
    if list_len == 0:
        return missing_version

    # Get latest index as full version of git
    installed_version = str(installed_version_split[list_len - 1])

    if installed_version == "":
        return missing_version

    return installed_version


def get_lfs_version():
    installed_version_split = pbtools.get_one_line_output([get_lfs_executable(), "--version"]).split(" ")

    if len(installed_version_split) == 0:
        return missing_version

    # Get first index as full version of git-lfs
    installed_version = str(installed_version_split[0])

    if installed_version == "":
        return missing_version

    return installed_version.split("/")[1]


def get_gcm_version():
    gcm_exec = get_gcm_executable()
    if gcm_exec is None:
        return missing_version
    if gcm_exec.startswith("diff"):
        return gcm_exec
    installed_version = pbtools.get_one_line_output([gcm_exec, "--version"])

    if installed_version == "":
        return missing_version

    # strip git commit
    installed_version = installed_version.split("+")[0]

    return installed_version


def get_lockables():
    lockables = set()
    lockables.update(pathlib.Path("Content").glob("**/*.uasset"))
    lockables.update(pathlib.Path("Content").glob("**/*.umap"))
    lockables.update(pathlib.Path("Plugins").glob("*/Content/**/*.uasset"))
    lockables.update(pathlib.Path("Plugins").glob("*/Content/**/*.umap"))
    return lockables


def get_locked(key="ours"):
    proc = pbtools.run_with_combined_output([get_lfs_executable(), "locks", "--verify", "--json"])
    if proc.returncode:
        return None
    locked_objects = json.loads(proc.stdout)[key]
    locked = set([l.get("path") for l in locked_objects])
    # also check untracked and added files
    proc = pbtools.run_with_combined_output([get_git_executable(), "status", "--porcelain"])
    if not proc.returncode:
        for line in proc.stdout.splitlines():
            if line[0] == "?" or line[1] == "?" or line[0] == "A" or line[1] == "A":
                locked.add(line[3:])
    return locked


def read_only(file):
        try:
            os.chmod(file, stat.S_IREAD)
            return None
        except OSError as e:
            return str(e)


def read_write(file):
        try:
            os.chmod(file, stat.S_IWRITE)
            return None
        except OSError as e:
            err_str = str(e)
            if "The system cannot find the file specified" in err_str:
                return f"You have a locked file which does not exist: {str(e.filename)}"
            else:
                return err_str


def fix_lfs_ro_attr():
    lockables = get_lockables()
    locked = get_locked()
    not_locked = lockables - locked
    with multiprocessing.Pool() as pool:
        for message in itertools.chain(pool.imap_unordered(read_only, not_locked, 100), pool.imap_unordered(read_write, locked)):
            if message:
                pblog.warning(message)


def set_tracking_information(upstream_branch_name: str):
    output = pbtools.get_combined_output([get_git_executable(), "branch", f"--set-upstream-to=origin/{upstream_branch_name}",
                                      upstream_branch_name])
    pblog.info(output)


def stash_pop():
    pblog.info("Popping stash...")

    output = pbtools.get_combined_output([get_git_executable(), "stash", "pop"])
    pblog.info(output)
    lower_case_output = output.lower()

    if pbtools.it_has_all(lower_case_output, "auto-merging", "conflict", "should have been pointers"):
        pbtools.error_state(f"git stash pop failed. Some of your stashed local changes would be overwritten by incoming changes. Request help in {pbconfig.get('support_channel')} to resolve conflicts, and please do not run UpdateProject until the issue is resolved.", True)
    elif "dropped refs" in lower_case_output:
        return
    elif "no stash entries found" in lower_case_output:
        return
    else:
        pbtools.error_state(f"git stash pop failed due to an unknown error. Request help in {pbconfig.get('support_channel')} to resolve possible conflicts, and please do not run UpdateProject until the issue is resolved.", True)


def get_remote_url():
    return pbconfig.get("git_url")


def check_remote_connection():
    current_url = pbtools.get_one_line_output([get_git_executable(), "remote", "get-url", "origin"])
    recent_url = pbconfig.get("git_url")

    if current_url != recent_url:
        output = pbtools.get_combined_output([get_git_executable(), "remote", "set-url", "origin", recent_url])
        current_url = recent_url
        pblog.info(output)

    out = pbtools.run_with_output([get_git_executable(), "ls-remote", "--exit-code", "-h"]).returncode
    return out == 0, current_url


def check_credentials():
    output = pbtools.get_one_line_output([get_git_executable(), "config", "user.name"])
    if output == "" or output is None:
        user_name = input("Please enter your GitHub username: ")
        pbtools.run_with_output([get_git_executable(), "config", "user.name", user_name])

    output = pbtools.get_one_line_output([get_git_executable(), "config", "user.email"])
    if output == "" or output is None:
        user_mail = input("Please enter your GitHub email: ")
        pbtools.run_with_output([get_git_executable(), "config", "user.email", user_mail])


def sync_file(file_path, sync_target=None):
    if sync_target is None:
        sync_target = f"origin/{get_current_branch_name()}"
    proc = pbtools.run([get_git_executable(), "restore", "-qWSs", sync_target, "--", file_path])
    return proc.returncode


def abort_all():
    # Abort everything
    pbtools.run_with_output([get_git_executable(), "merge", "--abort"])
    pbtools.run_with_output([get_git_executable(), "rebase", "--abort"])
    pbtools.run_with_output([get_git_executable(), "am", "--abort"])
    # Just in case
    shutil.rmtree(os.path.join(os.getcwd(), ".git", "rebase-apply"), ignore_errors=True)
    shutil.rmtree(os.path.join(os.getcwd(), ".git", "rebase-merge"), ignore_errors=True)


def abort_rebase():
    # Abort rebase
    pbtools.run_with_output([get_git_executable(), "rebase", "--abort"])


def setup_config():
    pbtools.run_with_output([get_git_executable(), "config", "include.path", "../.gitconfig"])


@lru_cache()
def get_credentials():
    repo_str = pbtools.get_one_line_output([get_git_executable(), "remote", "get-url", "origin"])
    repo_url = urlparse(repo_str)

    creds = f"protocol={repo_url.scheme}\n"
    creds += f"host={repo_url.hostname}\n"
    if repo_url.username:
        creds += f"username={repo_url.username}\n"
    creds += "\n"

    proc = pbtools.run_with_stdin([get_gcm_executable(), "get"], input=creds)

    if proc.returncode != 0:
        return (None, None)

    out = proc.stdout

    pairs = out.splitlines()
    kv = []
    for pair in pairs:
        if pair:
            kv.append(pair.split("=", 1))
    cred_dict = dict(kv)

    # force reauthentication
    if cred_dict.get("username") == "PersonalAccessToken":
        proc = pbtools.run_with_stdin([get_gcm_executable(), "erase"], input=creds)
        check_remote_connection()

    return cred_dict.get("username"), cred_dict.get("password")


def get_modified_files():
    proc = pbtools.run_with_output([get_git_executable(), "status", "--porcelain"])
    return [pathlib.Path(line[3:]) for line in proc.stdout.splitlines()]


def get_commits():
    proc = pbtools.run_with_combined_output([get_git_executable(), "log", "-100", "--no-merges", f"origin/{get_current_branch_name()}"])
    return proc.stdout
