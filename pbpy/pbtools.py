import os
from os import path
import psutil
import subprocess
import shutil
import stat

# PBSync Imports
from pbpy import pbunreal
from pbpy import pbconfig
from pbpy import pblog
from pbpy import pbgit

error_file = ".pbsync_err"

# True: Error on last run, False: No errors
def check_error_state():
    try:
        with open(error_file, 'r') as error_state_file:
            error_state = error_state_file.readline(1)
            if int(error_state) == 0:
                return False
            elif int(error_state) == 1:
                return True
            else:
                return False
    except:
        return False

def remove_file(file_path):
    try:
        os.remove(file_path)
    except:
        os.chmod(file_path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
        try:
            os.remove(file_path)
        except Exception as e:
            pblog.exception(str(e))
            pass
    return not os.path.isfile(file_path)

def error_state(msg = None, fatal_error = False):
    if msg != None:
        logging.error(msg)
    if fatal_error:
        # That was a fatal error, until issue is fixed, do not let user run PBSync
        with open(error_file, 'w') as error_state_file:
            error_state_file.write("1")
    out = input("Logs are saved in " + pbconfig.get("log_file_path") + ". Press enter to quit...")
    sys.exit(1)

def disable_watchman():
    subprocess.call(["git", "config", "--unset", "core.fsmonitor"])
    if check_running_process(pbconfig.get('watchman_executable_name')):
        os.system("taskkill /f /im " + pbconfig.get('watchman_executable_name'))

def enable_watchman():
    subprocess.call(["git", "config", "core.fsmonitor", "git-watchman/query-watchman"])
    # Trigger
    out = subprocess.getoutput(["git", "status"])

def push_build(branch_type):
    # Wrap executable with DRM
    result = subprocess.call([pbconfig.get('dispatch_executable_path'), "build", "drm-wrap", str(os.environ['DISPATCH_APP_ID']), pbconfig.get('dispatch_drm')])
    if result != 0:
        return False

    branch_id = "-1"
    if branch_type == "stable":
        branch_id = str(os.environ['DISPATCH_ALPHA_BID'])
    elif branch_type == "public":
        branch_id = str(os.environ['DISPATCH_BETA_BID'])
    else:
        return False

    # Push & Publish the build
    result = subprocess.call([pbconfig.get('dispatch_executable_path'), "build", "push", branch_id, pbconfig.get('dispatch_config'), pbconfig.get('dispatch_stagedir'), "-p"])
    return result == 0

def pbget_pull():
    os.chdir("PBGet")
    subprocess.call(["PBGet.exe", "resetcache"])
    status = subprocess.call(["PBGet.exe", "pull", "--threading", "false"])
    os.chdir("..")
    return status

def pbget_push(apikey):
    os.chdir("PBGet")
    status = subprocess.call(["PBGet.exe", "push", "--source", pbconfig.get('pbget_url'), "--apikey", apikey])
    os.chdir("..")
    return status

def check_running_process(process_name):
    try:
        if process_name in (p.name() for p in psutil.process_iter()):
            return True
    except:
        # An exception occured while checking, assume the program is not running
        pass
    return False

# TODO: Implement that into ue4versionator. Until doing that, this can stay inside pbunreal module
def is_versionator_symbols_enabled():
    if not path.isfile(pbconfig.get('versionator_config_path')):
        # Config file somehow isn't generated yet, only get a response, but do not write anything into config
        response = input("Do you want to also download debugging symbols for accurate crash logging? You can change that choice later in .ue4v-user config file [y/n]")
        if response == "y" or response == "Y":
            return True
        else:
            return False

    try:
        with open(pbconfig.get('versionator_config_path'), "r") as config_file:
            for ln in config_file:
                if "Symbols" in ln or "symbols" in ln:
                    if "False" in ln or "false" in ln:
                        return False
                    elif "True" in ln or "true" in ln:
                        return True
                    else:
                        # Incorrect config
                        return False
    except:
        return False

    # Symbols configuration variable is not on the file, let's add it
    try:
        with open(pbconfig.get('versionator_config_path'), "a+") as config_file:   
            response = input("Do you want to also download debugging symbols for accurate crash logging? You can change that choice later in .ue4v-user config file [y/n]")
            if response == "y" or response == "Y":
                config_file.write("\nsymbols = true")
                return True
            else:
                config_file.write("\nsymbols = false")
                return False
    except:
        return False

def run_ue4versionator():
    if is_versionator_symbols_enabled():
        return subprocess.call(["ue4versionator.exe", "--with-symbols"])
    else:
        return subprocess.call(["ue4versionator.exe"])

def get_path_total_size(start_path):
    total_size = -1
    try:
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except:
        return -1
    return total_size

def wipe_workspace():
    current_branch = pbgit.get_current_branch_name()
    response = input("This command will wipe your workspace and get latest changes from " + current_branch + ". Are you sure? [y/N]")
    
    if response != "y" and response != "Y":
        return False

    pbgit.abort_all()
    disable_watchman()
    subprocess.call(["git", "fetch", "origin", str(current_branch)])
    result = subprocess.call(["git", "reset", "--hard", "origin/" + str(current_branch)])
    subprocess.call(["git", "clean", "-fd"])
    subprocess.call(["git", "pull"])
    enable_watchman()
    return result == 0

def resolve_conflicts_and_pull():
    # Disable watchman for now
    disable_watchman()

    output = subprocess.getoutput(["git", "status"])
    pblog.info(str(output))

    pblog.info("Please wait while getting latest changes on the repository. It may take a while...")

    pblog.info("Trying to stash the local work...")
    output = subprocess.getoutput(["git", "stash"])
    pblog.info(str(output))

    pblog.info("Trying to rebase workspace with latest changes on the repository...")
    output = subprocess.getoutput(["git", "pull", "--rebase"])
    pblog.info(str(output))

    lower_case_output = str(output).lower()

    if "failed to merge in the changes" in lower_case_output or "could not apply" in lower_case_output:
        pblog.error("Aborting the rebase. Changes on one of your commits will be overridden by incoming changes. Request help on #tech-support to resolve conflicts, and  please do not run StartProject.bat until issue is solved.")
        pbgit.abort_rebase()
        pbgit.git_stash_pop()
        error_state(True)
    elif "fast-forwarded" in lower_case_output:
        pbgit.git_stash_pop()
        pblog.info("Success, rebased on latest changes without any conflict")
    elif "is up to date" in lower_case_output:
        pbgit.git_stash_pop()
        pblog.info("Success, rebased on latest changes without any conflict")
    elif "rewinding head" in lower_case_output and not("error" in lower_case_output or "conflict" in lower_case_output):
        pbgit.git_stash_pop()
        pblog.info("Success, rebased on latest changes without any conflict")
    else:
        pblog.error("Aborting the rebase, an unknown error occured. Request help on #tech-support to resolve conflicts, and please do not run StartProject.bat until issue is solved.")
        pbgit.abort_rebase()
        pbgit.git_stash_pop()
        error_state(True)

    # Run watchman back
    enable_watchman()