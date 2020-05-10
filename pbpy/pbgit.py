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
    pbtools.run_with_output(["git", "branch", f"--set-upstream-to=origin/{upstream_branch_name}", upstream_branch_name])


def check_remote_connection():
    current_url = pbtools.run_with_output(["git", "remote", "get-url", "origin"]).stdout
    recent_url = pbconfig.get("git_url")

    if current_url != recent_url:
        subprocess.run(["git", "remote", "set-url", "origin", recent_url])

    current_url = pbtools.run_with_output(["git", "remote", "get-url", "origin"]).stdout
    out = subprocess.run(["git", "ls-remote", "--exit-code", "-h"]).returncode
    return out == 0, str(current_url)


def check_credentials():
    output = str(subprocess.getoutput("git config user.name"))
    if output == "" or output is None:
        user_name = input("Please enter your GitHub username: ")
        subprocess.call(["git config", "user.name", user_name])

    output = str(subprocess.getoutput("git config user.email"))
    if output == "" or output is None:
        user_mail = input("Please enter your GitHub email: ")
        subprocess.call(["git", "config", "user.email", user_mail])


def sync_file(file_path):
    sync_head = f"origin/{get_current_branch_name()}"
    return subprocess.call(["git", "restore", "-qWSs", sync_head, "--", file_path])


def abort_all():
    # Abort everything
    out = subprocess.getoutput("git merge --abort")
    out = subprocess.getoutput("git rebase --abort")
    out = subprocess.getoutput("git am --abort")
    out = subprocess.getoutput("rm -rf .git/rebase-apply")


def abort_rebase():
    # Abort rebase
    out = subprocess.getoutput("git rebase --abort")


def setup_config():
    subprocess.call(["git", "config", "include.path", "../.gitconfig"])
    subprocess.call(["git", "config", pbconfig.get('lfs_lock_url'), "true"])

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
        subprocess.call(["git", "config", "--unset", cfg])
