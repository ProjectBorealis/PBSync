import os
import shutil
import subprocess

from pbpy import pblog
from pbpy import pbconfig
from pbpy import pbtools


def get_current_branch_name():
    try:
        return pbtools.run_with_output(["git", "branch", "--show-current"]).stdout
    except subprocess.CalledProcessError:
        pblog.error("Unknown error occurred.")


def get_git_version():
    installed_version_split = pbtools.run_with_output(["git", "--version"]).stdout.split(" ")

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
    installed_version_split = pbtools.run_with_output(["git-lfs", "--version"]).stdout.split(" ")

    if len(installed_version_split) == 0:
        return None

    # Get first index as full version of git-lfs
    installed_version = str(installed_version_split[0])

    if installed_version == "":
        return None

    return installed_version


def set_tracking_information(upstream_branch_name: str):
    subprocess.run(["git", "branch", f"--set-upstream-to=origin/{upstream_branch_name}", upstream_branch_name])


def stash_pop():
    pblog.info("Trying to pop stash...")

    run = pbtools.run_with_output(["git", "stash", "pop"])
    pblog.info(run.stdout)
    pblog.error(run.stderr)

    output = run.stdout + "\n" + run.stderr
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
    current_url = pbtools.run_with_output(["git", "remote", "get-url", "origin"]).stdout
    recent_url = pbconfig.get("git_url")

    if current_url != recent_url:
        subprocess.run(["git", "remote", "set-url", "origin", recent_url])

    current_url = pbtools.run_with_output(["git", "remote", "get-url", "origin"]).stdout
    out = subprocess.run(["git", "ls-remote", "--exit-code", "-h"]).returncode
    return out == 0, current_url


def check_credentials():
    output = pbtools.run_with_output(["git", "config", "user.name"]).stdout
    if output == "" or output is None:
        user_name = input("Please enter your GitHub username: ")
        subprocess.run(["git config", "user.name", user_name])

    output = pbtools.run_with_output(["git", "config", "user.email"]).stdout
    if output == "" or output is None:
        user_mail = input("Please enter your GitHub email: ")
        subprocess.run(["git", "config", "user.email", user_mail])


def sync_file(file_path):
    sync_head = f"origin/{get_current_branch_name()}"
    return subprocess.run(["git", "restore", "-qWSs", sync_head, "--", file_path]).returncode


def abort_all():
    # Abort everything
    subprocess.run(["git", "merge", "--abort"])
    subprocess.run(["git", "rebase", "--abort"])
    subprocess.run(["git", "am", "--abort"])
    # Just in case
    shutil.rmtree(os.path.join(os.getcwd(), ".git", "rebase-apply"))


def abort_rebase():
    # Abort rebase
    subprocess.run(["git", "rebase", "--abort"])


def setup_config():
    subprocess.run(["git", "config", "include.path", "../.gitconfig"])
    subprocess.run(["git", "config", pbconfig.get('lfs_lock_url'), "true"])

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
        subprocess.run(["git", "config", "--unset", cfg])
