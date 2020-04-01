import os
import sys
from os import path
from hashlib import md5
import psutil
import subprocess
import shutil
import stat
import json

# PBSync Imports
from pbpy import pbunreal
from pbpy import pbconfig
from pbpy import pblog
from pbpy import pbgit

error_file = ".pbsync_err"
watchman_exec_name = "watchman.exe"

def get_md5_hash(file_path):
    md5_reader = md5()
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            md5_reader.update(data)
            return str(md5_reader.hexdigest()).upper()
    except Exception as e:
        return None

def compare_md5_single(compared_file_path, md5_json_file_path):
    current_hash = get_md5_hash(compared_file_path)
    if current_hash is None:
        return False

    dict_search_string = ".\\" + compared_file_path
    hash_dict = get_dict_from_json(md5_json_file_path)

    if hash_dict is None or not (dict_search_string in hash_dict):
        pblog.error("Key " + dict_search_string + " not found in " + md5_json_file_path)
        return False

    if hash_dict[dict_search_string] == current_hash:
        pblog.info("MD5 checksum successful for " + compared_file_path)
        return True
    else:
        pblog.error("MD5 checksum failed for " + compared_file_path)
        pblog.error("Expected MD5: " + hash_dict[compared_file_path])
        pblog.error("Current MD5: " + str(current_hash))
        return False

def compare_md5_all(md5_json_file_path, print_log = False, ignored_extension = ".zip"):
    hash_dict = get_dict_from_json(md5_json_file_path)
    if hash_dict is None or len(hash_dict) == 0:
        return False

    is_success = True
    for file_path in hash_dict:
        if ignored_extension in file_path:
            continue
        current_md5 = get_md5_hash(file_path)
        if hash_dict[file_path] == current_md5:
            if print_log:
                pblog.info("MD5 checksum successful for " + file_path)
        else:
            if print_log:
                pblog.error("MD5 checksum failed for " + file_path)
                pblog.error("Expected MD5: " + hash_dict[file_path])
                pblog.error("Current MD5: " + str(current_md5))
            is_success = False
    return is_success
    
def get_dict_from_json(json_file_path):
    try:
        with open(json_file_path, 'rb') as json_file:
            json_text = json_file.read()
            return json.loads(json_text)
    except Exception as e:
        pblog.error(str(e))
        return None

def is_junction(path: str) -> bool:
    try:
        return bool(os.readlink(path))
    except OSError:
        return False

def remove_junction(destination):
    if os.path.isdir(destination):
        try:
            shutil.rmtree(destination)
        except:
            try:
                os.remove(destination)
            except:
                return False
    return True

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
        pblog.error(msg)
    if fatal_error:
        # That was a fatal error, until issue is fixed, do not let user run PBSync
        with open(error_file, 'w') as error_state_file:
            error_state_file.write("1")
    out = input("Logs are saved in " + pbconfig.get("log_file_path") + ". Press enter to quit...")
    sys.exit(1)

def disable_watchman():
    subprocess.call(["git", "config", "--unset", "core.fsmonitor"])
    if check_running_process(watchman_exec_name):
        os.system("taskkill /f /im " + watchman_exec_name)

def enable_watchman():
    subprocess.call(["git", "config", "core.fsmonitor", "git-watchman/query-watchman"])
    # Trigger
    out = subprocess.getoutput(["git", "status"])

def check_running_process(process_name):
    try:
        if process_name in (p.name() for p in psutil.process_iter()):
            return True
    except:
        # An exception occured while checking, assume the program is not running
        pass
    return False

# TODO: Implement that into ue4versionator. Until doing that, this can stay inside pbtool module
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

# TODO: Implement that into ue4versionator. Until doing that, this can stay inside pbtools module
def run_ue4versionator():
    if is_versionator_symbols_enabled():
        return subprocess.call(["ue4versionator.exe", "--with-symbols"])
    else:
        return subprocess.call(["ue4versionator.exe"])

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

    # Make sure upstream is tracked correctly
    pbgit.set_tracking_information(pbgit.get_current_branch_name())

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
        pbgit.stash_pop()
        error_state(True)
    elif "fast-forwarded" in lower_case_output:
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflict")
    elif "is up to date" in lower_case_output:
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflict")
    elif "rewinding head" in lower_case_output and not("error" in lower_case_output or "conflict" in lower_case_output):
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflict")
    elif "successfully rebased and updated" in lower_case_output:
        git_stash_pop()
        logging.info("Success, rebased on latest changes without any conflict")
    else:
        pblog.error("Aborting the rebase, an unknown error occured. Request help on #tech-support to resolve conflicts, and please do not run StartProject.bat until issue is solved.")
        pbgit.abort_rebase()
        pbgit.stash_pop()
        error_state(True)

    # Run watchman back
    enable_watchman()