import subprocess

from pbpy import pblog
from pbpy import pbconfig
from pbpy import pbtools


def get_current_branch_name():
    return str(subprocess.getoutput(["git", "branch", "--show-current"]))

def get_git_version():
    installed_version_split = subprocess.getoutput(["git", "--version"]).split(" ")

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
    installed_version_split = subprocess.getoutput(["git-lfs", "--version"]).split(" ")

    if len(installed_version_split) == 0:
        return None
    
    # Get first index as full version of git-lfs
    installed_version = str(installed_version_split[0])

    if installed_version == "":
        return None

    return installed_version

def set_tracking_information(upstream_branch_name: str):
    subprocess.call(["git", "branch", "--set-upstream-to=origin/" + upstream_branch_name, upstream_branch_name])

def stash_pop():
    pblog.info("Trying to pop stash...")

    output = subprocess.getoutput(["git", "stash", "pop"])
    pblog.info(str(output))

    lower_case_output = str(output).lower()

    if "auto-merging" in lower_case_output and "conflict" in lower_case_output and "should have been pointers" in lower_case_output:
        pbtools.error_state("""Git stash pop is failed. Some of your stashed local changes would be overwritten by incoming changes.
        Request help on #tech-support to resolve conflicts, and  please do not run StartProject.bat until issue is solved.""", True)
    elif "dropped refs" in lower_case_output:
        return
    elif "no stash entries found" in lower_case_output:
        return
    else:
        pbtools.error_state("""Git stash pop is failed due to unknown error. Request help on #tech-support to resolve possible conflicts, 
        and  please do not run StartProject.bat until issue is solved.""", True)

def check_remote_connection():
    current_url = subprocess.check_output(["git", "remote", "get-url", "origin"])
    recent_url = pbconfig.get("git_url")

    if current_url != recent_url:
        out = subprocess.check_output(["git", "remote", "set-url", "origin", recent_url])

    current_url = subprocess.check_output(["git", "remote", "get-url", "origin"])
    out = subprocess.check_output(["git", "ls-remote", "--exit-code", "-h"])
    return not ("fatal" in str(out)), str(current_url)

def check_credentials():
    output = str(subprocess.getoutput(["git", "config", "user.name"]))
    if output == "" or output == None:
        user_name = input("Please enter your Github username: ")
        subprocess.call(["git", "config", "user.name", user_name])

    output = str(subprocess.getoutput(["git", "config", "user.email"]))
    if output == "" or output == None:
        user_mail = input("Please enter your Github e-mail: ")
        subprocess.call(["git", "config", "user.email", user_mail])

def sync_file(file_path):
    sync_head = "origin/" + get_current_branch_name()
    return subprocess.call(["git", "checkout", "-f", sync_head, "--", file_path])

def abort_all():
    # Abort everything
    out = subprocess.getoutput(["git", "merge", "--abort"])
    out = subprocess.getoutput(["git", "rebase", "--abort"])
    out = subprocess.getoutput(["git", "am", "--abort"])

def abort_rebase():
    # Abort rebase
    out = subprocess.getoutput(["git", "rebase", "--abort"])

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
