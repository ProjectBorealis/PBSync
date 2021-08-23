import os
import sys
import time
import psutil
import subprocess
import shutil
import stat
import json
import threading
import hashlib

from subprocess import CalledProcessError
from pathlib import Path

# PBSync Imports
from pbpy import pbconfig
from pbpy import pblog
from pbpy import pbgit
from pbpy import pbunreal
from pbpy import pbuac

error_file = ".pbsync_err"


def handle_env(env):
    if env is None:
        return os.environ
    else:
        return os.environ | env
    

def handle_env_out(cmd, env_out):
    if env_out:
        for env_var in env_out:
            if os.name == "posix":
                cmd.extend(["&&", "echo", f"{env_var}=${env_var}"])
            else:    
                cmd.extend(["&&", "set", env_var])


def parse_environment(stdout, env_out):
    if env_out is None:
        return
    for line in stdout.splitlines():
        # if not a valid line for environment echo, skip it
        if line.startswith("?") or line.startswith("Environment variable "):
            continue
        k, _, v = line.partition('=')
        # v is empty if no partition (not a key=value) or no value set (key=)
        # must check to see if we actually requested this key
        # then, check if this was a set variable in posix
        if v and k in env_out and not v.startswith("$"):
            os.environ[k] = v.strip('"')


def run(cmd, env=None):
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    env = handle_env(env)
    return subprocess.run(cmd, shell=True, env=env)


def run_with_output(cmd, env=None, env_out=None):
    handle_env_out(cmd, env_out)
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    env = handle_env(env)
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=True, env=env)
    parse_environment(proc.stdout, env_out)
    return proc


def run_stream(cmd, env=None):
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    proc = subprocess.Popen(cmd, text=True, shell=True, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    returncode = None
    while True:
        # TODO: handle encoding
        try:
            for line in iter(lambda: proc.stdout.readline(), ''):
                pblog.info(line)
        except:
            continue
        returncode = proc.poll()
        if returncode is not None:
            break
    return proc


def run_with_stdin(cmd, input, env=None, env_out=None):
    handle_env_out(cmd, env_out)
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    env = handle_env(env)
    proc = subprocess.run(cmd, input=input, capture_output=True, text=True, shell=True, env=env)
    parse_environment(proc.stdout, env_out)
    return proc


def run_with_combined_output(cmd, env=None, env_out=None):
    handle_env_out(cmd, env_out)
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    env = handle_env(env)
    proc = subprocess.run(cmd, text=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    parse_environment(proc.stdout, env_out)
    return proc


def run_non_blocking(*commands):
    if os.name == "nt":
        cmdline = " & ".join(commands)
        subprocess.Popen(cmdline, shell=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elif os.name == "posix":
        forked_commands = [f"nohup {command}" for command in commands]
        cmdline = " || ".join(forked_commands)
        subprocess.Popen(cmdline, shell=True, start_new_session=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def get_combined_output(cmd, env=None, env_out=None):
    return run_with_combined_output(cmd, env=env, env_out=env_out).stdout


def get_one_line_output(cmd, env=None, env_out=None):
    return run_with_output(cmd, env=env, env_out=env_out).stdout.rstrip()


def it_has_any(it, *args):
    return any([el in it for el in args])


def it_has_all(it, *args):
    return all([el in it for el in args])


def whereis(app):
    result = None

    command = 'where'
    if os.name != "nt":
        command = 'which'

    try:
        result = subprocess.run(f"{command} {app}", text=True, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    except CalledProcessError:
        pass

    if result is None:
        return []

    result = result.splitlines()
    return [Path(line) for line in result if len(line)]


def get_hash(file_path):
    hash_reader = hashlib.blake2b()
    try:
        with open(file_path, "rb") as f:
            hash_reader.update(f.read())
            return str(hash_reader.hexdigest())
    except FileNotFoundError:
        return None
    except Exception as e:
        pblog.exception(str(e))
        return None


def compare_hash_single(compared_file_path, hash_json_file_path):
    current_hash = get_hash(compared_file_path)
    if current_hash is None:
        return False

    dict_search_string = f"{compared_file_path}"
    hash_dict = get_dict_from_json(hash_json_file_path)

    if hash_dict is None or not (dict_search_string in hash_dict):
        pblog.error(f"Key {dict_search_string} not found in {hash_json_file_path}")
        return False

    if hash_dict[dict_search_string] == current_hash:
        pblog.info(f"Checksum successful for {compared_file_path}")
        return True
    else:
        pblog.error(f"Checksum failed for {compared_file_path}")
        pblog.error(f"Expected hash: {hash_dict[dict_search_string]}")
        pblog.error(f"Current hash: {str(current_hash)}")
        return False


def compare_hash_all(hash_json_file_path, print_log=False, ignored_extension=".zip"):
    hash_dict = get_dict_from_json(hash_json_file_path)
    if hash_dict is None or len(hash_dict) == 0:
        return False

    for file_path in hash_dict:
        if file_path.endswith(ignored_extension):
            continue
        
        current_hash = get_hash(file_path)
        if hash_dict[file_path] == current_hash:
            if print_log:
                pblog.info(f"Checksum successful for {file_path}")
        else:
            if print_log:
                pblog.error(f"Checksum failed for {file_path}")
                if current_hash is not None:
                    pblog.error(f"Expected hash: {hash_dict[file_path]}")
                    pblog.error(f"Current hash: {str(current_hash)}")
                else:
                    pblog.error("File does not exist")
            return False
    return True


def make_json_from_dict(dictionary, json_file_path):
    with open(json_file_path, "w") as f:
        json.dump(dictionary, f)


def get_dict_from_json(json_file_path):
    try:
        with open(json_file_path, 'rb') as json_file:
            json_text = json_file.read()
            return json.loads(json_text)
    except Exception as e:
        pblog.exception(str(e))
        return None


def is_junction(file_path: str) -> bool:
    try:
        return bool(os.readlink(file_path))
    except OSError:
        return False
    except ValueError:
        return False
    except NotImplementedError:
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


def error_state(msg=None, fatal_error=False, hush=False, term=False):
    if msg is not None:
        pblog.error(msg)
    if fatal_error:
        # Log status for more information during tech support
        pblog.info(run_with_combined_output([pbgit.get_git_executable(), "status"]).stdout)
        # This is a fatal error, so do not let user run PBSync until issue is fixed
        with open(error_file, 'w') as error_state_file:
            error_state_file.write("1")
    if not hush:
        pblog.info(f"Logs are saved in {pbconfig.get('log_file_path')}.")
    if not term:
        pbconfig.shutdown()
    sys.exit(1)


def get_running_process(process_name):
    if os.name == "nt":
        process_name += ".exe"
    try:
        for p in psutil.process_iter(["name", "exe"]):
            if process_name == p.info["name"]:
                return p
    except Exception:
        # An exception occurred while checking, assume the program is not running
        pass
    return None


def wipe_workspace():
    current_branch = pbgit.get_current_branch_name()
    response = input(f"This command will wipe your workspace and get latest changes from {current_branch}. Are you sure? [y/N] ")

    if len(response) < 1 or response[0].lower() != "y":
        return False

    pbgit.abort_all()
    output = get_combined_output([pbgit.get_git_executable(), "fetch", "origin", current_branch])
    pblog.info(output)
    proc = run_with_combined_output([pbgit.get_git_executable(), "reset", "--hard", f"origin/{current_branch}"])
    result = proc.returncode
    pblog.info(proc.stdout)
    output = get_combined_output([pbgit.get_git_executable(), "clean", "-fd"])
    pblog.info(output)
    output = get_combined_output([pbgit.get_git_executable(), "pull"])
    pblog.info(output)
    return result == 0


def maintain_repo():
    pblog.info("Starting repo maintenance...")

    commands = [
        f"{pbgit.get_lfs_executable()} prune -c",
        f"{pbgit.get_lfs_executable()} dedup"
    ]

    if os.name == "nt":
        proc = run_with_combined_output(["schtasks" "/query", "/TN", "Git for Windows Updater"])
        # if exists
        if proc.returncode == 0:
            cmdline = ["schtasks", "/delete", "/F", "/TN", "\"Git for Windows Updater\""]
            if not pbuac.isUserAdmin():
                pbuac.runAsAdmin(cmdline)
            else:
                proc = run_with_combined_output(cmdline)

    does_maintainence = get_one_line_output([pbgit.get_git_executable(), "config", "maintenance.prefetch.schedule"]) == "hourly"
    if not does_maintainence:
        commands.insert(0, f"scalar register .")

    # fill in the git repo optionally
    is_shallow = get_one_line_output([pbgit.get_git_executable(), "rev-parse", "--is-shallow-repository"])
    # add in the front, so everything else can clean up after the fetch
    if is_shallow == "true":
        pblog.info("Shallow clone detected. PBSync will fill in history in the background.")
        commands.insert(0, f"{pbgit.get_git_executable()} fetch --unshallow")

    run_non_blocking(*commands)


lfs_fetch_thread = None


def do_lfs_fetch():
    branch_name = pbgit.get_current_branch_name()
    run_with_combined_output([pbgit.get_lfs_executable(), "fetch", "origin", f"origin/{branch_name}"])


def start_lfs_fetch():
    pblog.info("Starting LFS fetch...")
    global lfs_fetch_thread
    lfs_fetch_thread = threading.Thread(target=do_lfs_fetch)
    lfs_fetch_thread.start()


def finish_lfs_fetch():
    pblog.info("Finishing LFS fetch...")
    lfs_fetch_thread.join()
    pblog.info("Finished LFS fetch.")


def resolve_conflicts_and_pull(retry_count=0, max_retries=1):
    branch_name = pbgit.get_current_branch_name()
    if branch_name not in pbconfig.get("branches"):
        return

    def should_attempt_auto_resolve():
        return retry_count <= max_retries

    if retry_count:
        # wait a little bit if retrying (exponential)
        time.sleep(0.25 * (1 << retry_count))

    out = get_combined_output([pbgit.get_git_executable(), "status", "--porcelain=2", "--branch"])

    if not it_has_any(out, "-0"):
        start_lfs_fetch()
        pbunreal.ensure_ue_closed()
        pblog.info("Please wait while getting the latest changes from the repository. It may take a while...")        
        
        # Get the latest files, but skip smudge so we can super charge a LFS pull as one batch
        cmdline = [pbgit.get_git_executable(), "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=", "-c", "filter.lfs.required=false"]
        # if we can fast forward merge, do that instead of a rebase (faster, safer)
        if it_has_any(out, "+0"):
            pblog.info("Fast forwarding workspace to the latest changes from the repository...")
            cmdline.extend(["merge", "--ff-only"])
        else:
            pblog.info("Rebasing workspace with the latest changes from the repository...")
            cmdline.extend(["rebase", "--autostash"])
        cmdline.append(f"origin/{branch_name}")
        result = run_with_combined_output(cmdline)
        # Checkout LFS in one go since we skipped smudge and fetched in the background
        finish_lfs_fetch()
        run_with_combined_output([pbgit.get_lfs_executable(), "checkout"])
        # update plugin submodules
        run_with_combined_output([pbgit.get_git_executable(), "submodule", "update", "--init", "--", "Plugins"])
        code = result.returncode
        out = result.stdout
        pblog.info(out)
        out = out.lower()
        error = code != 0
    else:
        error = False

    def handle_success():
        pblog.success("Success! You are now on the latest changes without any conflicts.")

    def handle_error(msg=None):
        error_state(msg, fatal_error=True)

    if not error:
        handle_success()
    elif "fast-forward" in out:
        handle_success()
    elif "up to date" in out:
        handle_success()
    elif "rewinding head" in out and not it_has_any(out, "error", "conflict"):
        handle_success()
    elif "successfully rebased and updated" in out:
        handle_success()
    elif it_has_any(out, "failed to merge in the changes", "could not apply"):
        handle_error(f"Aborting the rebase. Changes on one of your commits will be overridden by incoming changes. Please request help in {pbconfig.get('support_channel')} to resolve conflicts, and please do not run UpdateProject until the issue is resolved.")
    elif it_has_any(out, "unmerged files", "merge_head exists"):
        error_state(f"You are in the middle of a merge. Please request help in {pbconfig.get('support_channel')} to resolve it, and please do not run UpdateProject until the issue is resolved.", fatal_error=True)
    elif "unborn" in out:
        if should_attempt_auto_resolve():
            pblog.error("Unborn branch detected. Retrying...")
            retry_count += 1
            resolve_conflicts_and_pull(retry_count)
            return
        else:
            handle_error(f"You are on an unborn branch. Please request help in {pbconfig.get('support_channel')} to resolve it, and please do not run UpdateProject until the issue is resolved.")
    elif it_has_any(out, "no remote", "no such remote", "refspecs without repo"):
        if should_attempt_auto_resolve():
            pblog.error("Remote repository not found. Retrying...")
            retry_count += 1
            resolve_conflicts_and_pull(retry_count, 2)
            return
        else:
            handle_error(f"The remote repository could not be found. Please request help in {pbconfig.get('support_channel')} to resolve it, and please do not run UpdateProject until the issue is resolved.")
    elif "cannot open" in out:
        if should_attempt_auto_resolve():
            pblog.error("Git file info could not be read. Retrying...")
            retry_count += 1
            resolve_conflicts_and_pull(retry_count, 3)
            return
        else:
            handle_error(f"Git file info could not be read. Please request help in {pbconfig.get('support_channel')} to resolve it, and please do not run UpdateProject until the issue is resolved.")
    else:
        # We have no idea what the state of the repo is. Do nothing except bail.
        error_state(f"Aborting the repo update because of an unknown error. Request help in {pbconfig.get('support_channel')} to resolve it, and please do not run UpdateProject until the issue is resolved.", fatal_error=True)

    maintain_repo()
