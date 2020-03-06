import pblog
import pbconfig

def get_git_version():
    installed_version = subprocess.getoutput(["git", "--version"])
    installed_version_parsed = re.findall("(\d+)\.(\d+)\.(\d)", str(installed_version))

    if len(installed_version_parsed) == 0 or len(installed_version_parsed[0]) == 0:
        return ""

    return installed_version_parsed[0]

def get_lfs_version():
    installed_version = subprocess.getoutput(["git-lfs", "--version"])
    installed_version_parsed = re.findall("(\d+)\.(\d+)\.(\d)", str(installed_version))
    if len(installed_version_parsed) == 0 or len(installed_version_parsed[0]) == 0:
        return ""

    # Index 0 is lfs version, other matched version is Go compiler version
    return installed_version_parsed[0]

def stash_pop():
    logging.info("Trying to pop stash...")

    output = subprocess.getoutput(["git", "stash", "pop"])
    logging.info(str(output))

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
        subprocess.call(["git", "remote", "set-url", "origin", recent_url])

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
  subprocess.call(["git", "config", pbconfig.get('lfs_lock_url'), "true"])
  subprocess.call(["git", "config", "core.hooksPath", pbconfig.get('git_hooks_path')])
  subprocess.call(["git", "config", "include.path", "../.gitconfig"])

def get_current_branch_name():
    return str(subprocess.getoutput(["git", "branch", "--show-current"]))

# -2: Parse error
# -1: Old version
# 0: Expected version
# 1: Newer version
def compare_git_version(compared_version):
    installed_version = get_git_version()
    if len(installed_version) != 3:
        return -2
    
    expected_version = str(compared_version).split(".")
    if len(expected_version) != 3:
        return -2

    if int(installed_version[0]) == int(expected_version[0]) and int(installed_version[1]) == int(expected_version[1]) and int(installed_version[2]) == int(expected_version[2]):
        # Same version
        return 0
    
    # Not same version:
    if int(installed_version[0]) < int(expected_version[0]):
        return -1
    elif int(installed_version[1]) < int(expected_version[1]):
        return -1
    elif int(installed_version[2]) < int(expected_version[2]):
        return -1
    
    # Not older version:
    if int(installed_version[0]) > int(expected_version[0]):
        return 1
    elif int(installed_version[1]) > int(expected_version[1]):
        return 1
    elif int(installed_version[2]) > int(expected_version[2]):
        return 1

    # Something went wrong, return parse error
    return -2

# -2: Parse error
# -1: Old version
# 0: Expected version
# 1: Newer version
def compare_lfs_version(compared_version):
    installed_version = get_lfs_version()
    if len(installed_version) != 3:
        return -2
    
    expected_version = str(compared_version).split(".")
    if len(installed_version) != 3:
        return -2
    
    if int(installed_version[0]) == int(expected_version[0]) and int(installed_version[1]) == int(expected_version[1]) and int(installed_version[2]) == int(expected_version[2]):
        # Same version
        return 0
    
    # Not same version:
    if int(installed_version[0]) < int(expected_version[0]):
        return -1
    elif int(installed_version[1]) < int(expected_version[1]):
        return -1
    elif int(installed_version[2]) < int(expected_version[2]):
        return -1
    
    # Not older version:
    if int(installed_version[0]) > int(expected_version[0]):
        return 1
    elif int(installed_version[1]) > int(expected_version[1]):
        return 1
    elif int(installed_version[2]) > int(expected_version[2]):
        return 1

    # Something went wrong, return parse error
    return -2