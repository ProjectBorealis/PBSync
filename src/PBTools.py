import os
import os.path
import psutil
import subprocess
import shutil

# PBSync Imports
import pbunreal
import pbconfig

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

def run_ue4versionator():
    if pbparser.is_versionator_symbols_enabled():
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

