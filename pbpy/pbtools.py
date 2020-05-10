import os
import sys
import time
from hashlib import md5
import psutil
import subprocess
import shutil
import stat
import json

# PBSync Imports
from pbpy import pbconfig
from pbpy import pblog
from pbpy import pbgit

error_file = ".pbsync_err"
watchman_exec_name = "watchman.exe"


def run_with_output(*cmd):
    return subprocess.run(*cmd, capture_output=True, text=True)


def run_with_combined_output(*cmd):
    return subprocess.run(*cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def get_combined_output(*cmd):
    return run_with_combined_output(*cmd).stderr


def get_md5_hash(file_path):
    md5_reader = md5()
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            md5_reader.update(data)
            return str(md5_reader.hexdigest()).upper()
    except Exception as e:
        pblog.exception(str(e))
        return None


def compare_md5_single(compared_file_path, md5_json_file_path):
    current_hash = get_md5_hash(compared_file_path)
    if current_hash is None:
        return False

    dict_search_string = f".\\{compared_file_path}"
    hash_dict = get_dict_from_json(md5_json_file_path)

    if hash_dict is None or not (dict_search_string in hash_dict):
        pblog.error(f"Key {dict_search_string} not found in {md5_json_file_path}")
        return False

    if hash_dict[dict_search_string] == current_hash:
        pblog.info(f"MD5 checksum successful for {compared_file_path}")
        return True
    else:
        pblog.error(f"MD5 checksum failed for {compared_file_path}")
        pblog.error(f"Expected MD5: {hash_dict[compared_file_path]}")
        pblog.error(f"Current MD5: {str(current_hash)}")
        return False


def compare_md5_all(md5_json_file_path, print_log=False, ignored_extension=".zip"):
    hash_dict = get_dict_from_json(md5_json_file_path)
    if hash_dict is None or len(hash_dict) == 0:
        return False

    is_success = True
    for file_path in hash_dict:
        if not os.path.isfile(file_path):
            # If file doesn't exist, that means we fail the checksum
            if print_log:
                pblog.error(f"MD5 checksum failed for {file_path}")
                pblog.error("File does not exist")
            return False

        if ignored_extension in file_path:
            continue
        current_md5 = get_md5_hash(file_path)
        if hash_dict[file_path] == current_md5:
            if print_log:
                pblog.info(f"MD5 checksum successful for {file_path}")
        else:
            if print_log:
                pblog.error(f"MD5 checksum failed for {file_path}")
                pblog.error(f"Expected MD5: {hash_dict[file_path]}")
                pblog.error(f"Current MD5: {str(current_md5)}")
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


def is_junction(file_path: str) -> bool:
    try:
        return bool(os.readlink(file_path))
    except OSError:
        return False


def remove_junction(destination):
    if os.path.isdir(destination):
        try:
            shutil.rmtree(destination)
        except Exception:
            try:
                os.remove(destination)
            except Exception:
                return False
    return True


def check_error_state():
    # True: Error on last run, False: No errors
    try:
        with open(error_file) as error_state_file:
            error_code = error_state_file.readline(1)
            if int(error_code) == 0:
                return False
            elif int(error_code) == 1:
                return True
            else:
                return False
    except Exception:
        return False


def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception:
        os.chmod(file_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        try:
            os.remove(file_path)
        except Exception as e:
            pblog.exception(str(e))
            pass
    return not os.path.isfile(file_path)


def error_state(msg=None, fatal_error=False):
    if msg is not None:
        pblog.error(msg)
    if fatal_error:
        # That was a fatal error, until issue is fixed, do not let user run PBSync
        with open(error_file, 'w') as error_state_file:
            error_state_file.write("1")
    pblog.info(f"Logs are saved in {pbconfig.get('log_file_path')}. Press enter to quit...")
    sys.exit(1)


def disable_watchman():
    subprocess.run(["git", "config", "--unset", "core.fsmonitor"])
    if check_running_process(watchman_exec_name):
        subprocess.run(f"taskkill /f /im {watchman_exec_name}", shell=True)


def check_running_process(process_name):
    try:
        if process_name in (p.name() for p in psutil.process_iter()):
            return True
    except Exception:
        # An exception occurred while checking, assume the program is not running
        pass
    return False


def wipe_workspace():
    current_branch = pbgit.get_current_branch_name()
    response = input(f"This command will wipe your workspace and get latest changes from {current_branch}. Are you sure? [y/N]")

    if response != "y" and response != "Y":
        return False

    pbgit.abort_all()
    disable_watchman()
    subprocess.run(["git", "fetch", "origin", current_branch])
    result = subprocess.run(["git", "reset", "--hard", f"origin/{current_branch}"]).returncode
    subprocess.run(["git", "clean", "-fd"])
    subprocess.run(["git", "pull"])
    return result == 0


def resolve_conflicts_and_pull(retry_count=0, max_retries=1):
    def should_attempt_auto_resolve():
        return retry_count <= max_retries

    if retry_count:
        # wait a little bit if retrying (exponential)
        time.sleep(0.25 * (1 << retry_count))

    # Disable watchman for now
    disable_watchman()

    out = get_combined_output(["git", "status"])
    pblog.info(out)

    pblog.info("Please wait while getting the latest changes from the repository. It may take a while...")

    # Make sure upstream is tracked correctly
    pbgit.set_tracking_information(pbgit.get_current_branch_name())

    pblog.info("Trying to stash the local work...")
    output = run_with_combined_output(["git", "stash"])
    pblog.info(output)
    pblog.info("Trying to rebase workspace with latest changes on the repository...")
    result = run_with_output(["git", "pull", "--rebase", "--no-autostash"])
    # TODO: autostash handling
    # pblog.info("Trying to rebase workspace with latest changes on the repository...")
    # result = run_with_output(["git", "pull", "--rebase", "--autostash"])
    code = result.returncode
    pblog.info(result.stdout)
    err = result.stderr
    error = code != 0
    if err is not None and err != "":
        pblog.error(err)
        error = True

    out = f"{result.stdout}\n{result.stderr}"
    out = out.lower()

    if not error:
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflicts")
    elif "fast-forwarded" in out:
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflicts")
    elif "is up to date" in out:
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflicts")
    elif "rewinding head" in out and not ("error" in out or "conflict" in out):
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflicts")
    elif "successfully rebased and updated" in out:
        pbgit.stash_pop()
        pblog.info("Success, rebased on latest changes without any conflicts")
    elif "failed to merge in the changes" in out or "could not apply" in out:
        pblog.error("Aborting the rebase. Changes on one of your commits will be overridden by incoming changes. Request help in #tech-support to resolve conflicts, and please do not run StartProject.bat until the issue is resolved.")
        pbgit.abort_rebase()
        pbgit.stash_pop()
        error_state(fatal_error=True)
    elif "unmerged files" in out or "merge_head exists" in out:
        error_state(fatal_error=True)
    elif "unborn" in out:
        if should_attempt_auto_resolve():
            pblog.error("Unborn branch detected. Retrying...")
            resolve_conflicts_and_pull(++retry_count)
        else:
            pblog.error("You are on an unborn branch. Please request help in #tech-support to resolve it, and please do not run StartProject.bat until the issue is resolved.")
            error_state(fatal_error=True)
    elif "no remote" in out or "no such remote" in out or "refspecs without repo" in out:
        if should_attempt_auto_resolve():
            pblog.error("Remote repository not found. Retrying...")
            resolve_conflicts_and_pull(++retry_count, 2)
        else:
            pblog.error("The remote repository could not be found. Please request help in #tech-support to resolve it, and please do not run StartProject.bat until the issue is resolved.")
            error_state(fatal_error=True)
    elif "cannot open" in out:
        if should_attempt_auto_resolve():
            pblog.error("Git file info could not be read. Retrying...")
            resolve_conflicts_and_pull(++retry_count, 3)
    else:
        pblog.error("Aborting the repo update because of an unknown error. Request help in #tech-support to resolve it, and please do not run StartProject.bat until the issue is resolved.")
        pbgit.abort_rebase()
        error_state(fatal_error=True)

    # TODO: background prune
    # pblog.info("Cleaning up unused repository assets...")
    # subprocess.run(["git", "lfs", "prune", "-c"])
