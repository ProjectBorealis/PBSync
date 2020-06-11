import os
import shutil
import subprocess

from functools import lru_cache
from pbpy import pblog
from pbpy import pbconfig
from pbpy import pbtools


@lru_cache()
def get_current_branch_name():
    return pbtools.get_one_line_output(["git", "branch", "--show-current"])


def get_git_version():
    installed_version_split = pbtools.get_one_line_output(["git", "--version"]).split(" ")

    list_len = len(installed_version_split)
    if list_len == 0:
        return None

    # Get latest index as full version of git
    installed_version = str(installed_version_split[list_len - 1])

    if installed_version == "":
        return None

    return installed_version


def compare_with_current_branch_name(compared_branch):
    return get_current_branch_name() == compared_branch


def get_lfs_version():
    installed_version_split = pbtools.get_one_line_output(["git", "lfs", "--version"]).split(" ")

    if len(installed_version_split) == 0:
        return None

    # Get first index as full version of git-lfs
    installed_version = str(installed_version_split[0])

    if installed_version == "":
        return None

    return installed_version


def set_tracking_information(upstream_branch_name: str):
    output = pbtools.get_combined_output(["git", "branch", f"--set-upstream-to=origin/{upstream_branch_name}",
                                      upstream_branch_name])
    pblog.info(output)


def stash_pop():
    pblog.info("Trying to pop stash...")

    output = pbtools.get_combined_output(["git", "stash", "pop"])
    pblog.info(output)
    lower_case_output = output.lower()

    if "auto-merging" in lower_case_output and "conflict" in lower_case_output and "should have been pointers" in lower_case_output:
        pbtools.error_state("""git stash pop failed. Some of your stashed local changes would be overwritten by incoming changes.
        Request help in #tech-support to resolve conflicts, and please do not run StartProject.bat until the issue is resolved.""", True)
    elif "dropped refs" in lower_case_output:
        return
    elif "no stash entries found" in lower_case_output:
        return
    else:
        pbtools.error_state("""git stash pop failed due to an unknown error. Request help in #tech-support to resolve possible conflicts, 
        and please do not run StartProject.bat until the issue is resolved.""", True)


def check_remote_connection():
    current_url = pbtools.get_one_line_output(["git", "remote", "get-url", "origin"])
    recent_url = pbconfig.get("git_url")

    if current_url != recent_url:
        output = pbtools.get_combined_output(["git", "remote", "set-url", "origin", recent_url])
        pblog.info(output)

    current_url = pbtools.get_one_line_output(["git", "remote", "get-url", "origin"])
    out = pbtools.run_with_output(["git", "ls-remote", "--exit-code", "-h"]).returncode
    return out == 0, current_url


def check_credentials():
    output = pbtools.get_one_line_output(["git", "config", "user.name"])
    if output == "" or output is None:
        user_name = input("Please enter your GitHub username: ")
        pbtools.run_with_output(["git", "config", "user.name", user_name])

    output = pbtools.get_one_line_output(["git", "config", "user.email"])
    if output == "" or output is None:
        user_mail = input("Please enter your GitHub email: ")
        pbtools.run_with_output(["git", "config", "user.email", user_mail])


def sync_file(file_path):
    sync_head = f"origin/{get_current_branch_name()}"
    proc = subprocess.run(["git", "restore", "-qWSs", sync_head, "--", file_path], shell=True)
    return proc.returncode


def abort_all():
    # Abort everything
    pbtools.run_with_output(["git", "merge", "--abort"])
    pbtools.run_with_output(["git", "rebase", "--abort"])
    pbtools.run_with_output(["git", "am", "--abort"])
    # Just in case
    shutil.rmtree(os.path.join(os.getcwd(), ".git", "rebase-apply"), ignore_errors=True)


def abort_rebase():
    # Abort rebase
    pbtools.run_with_output(["git", "rebase", "--abort"])


def setup_config():
    pbtools.run_with_output(["git", "config", "include.path", "../.gitconfig"])
    pbtools.run_with_output(["git", "config", pbconfig.get('lfs_lock_url'), "true"])

    # Temporary code to clear previous git config variables:
    clear_config_list = [
        "core.hookspath",
        "core.autocrlf",
        "core.multipackindex",
        "core.fsmonitor",
        "commit.template",
        "merge.diffstyle",
        "push.default",
        "blame.coloring",
        "fetch.prune",
        "fetch.prunetags",
        "help.autocorrect",
        "index.threads",
        "pack.threads",
        "pack.usesparse",
        "protocol.version",
        "pull.rebase",
        "repack.writebitmaps",
        "rerere.autoupdate",
        "rerere.enabled"
    ]

    for cfg in clear_config_list:
        pbtools.run_with_output(["git", "config", "--unset", cfg])
