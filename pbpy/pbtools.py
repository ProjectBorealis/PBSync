import os
import sys
import time
import psutil
import subprocess
import shutil
import stat
import json
import datetime

from hashlib import md5
from subprocess import CalledProcessError
from pathlib import Path

# PBSync Imports
from pbpy import pbconfig
from pbpy import pblog
from pbpy import pbgit
from pbpy import pbunreal

error_file = ".pbsync_err"


def run(cmd, env=None):
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    if env is None:
        env = os.environ
    else:
        env = os.environ | env
    return subprocess.run(cmd, shell=True, env=env)


def run_with_output(cmd, env=None):
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    if env is None:
        env = os.environ
    else:
        env = os.environ | env
    return subprocess.run(cmd, capture_output=True, text=True, shell=True, env=env)


def run_with_combined_output(cmd, env=None):
    if os.name == "posix":
        cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

    if env is None:
        env = os.environ
    else:
        env = os.environ | env
    return subprocess.run(cmd, text=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)


def run_non_blocking(*commands):
    if os.name == "nt":
        cmdline = " & ".join(commands)
        subprocess.Popen(cmdline, shell=True, creationflags=subprocess.DETACHED_PROCESS)
    elif os.name == "posix":
        forked_commands = [f"nohup {command}" for command in commands]
        cmdline = " || ".join(forked_commands)
        subprocess.Popen(cmdline, shell=True)


def get_combined_output(cmd, env=None):
    return run_with_combined_output(cmd, env=env).stdout


def get_one_line_output(cmd, env=None):
    return run_with_output(cmd, env=env).stdout.rstrip()


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
        pblog.error(f"Expected MD5: {hash_dict[dict_search_string]}")
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

    expire_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%x")

    # try to remove commit graph lock before running commit graph
    do_commit_graph = True
    try:
        commit_graph_lock = os.path.join(os.getcwd(), ".git", "objects", "info", "commit-graphs", "commit-graph-chain.lock")
        if (os.path.exists(commit_graph_lock)):
            os.remove(commit_graph_lock)
    except Exception as e:
        pblog.exception(str(e))
        do_commit_graph = False

    commands = [
        f"{pbgit.get_git_executable()} maintenance --task gc --task loose-objects",
        f"{pbgit.get_lfs_executable()} prune -c",
        f"{pbgit.get_lfs_executable()} dedup"
    ]

    if do_commit_graph:
        commands.insert(1, f"{pbgit.get_git_executable()} commit-graph write --split --size-multiple=4 --reachable --changed-paths --expire-time={expire_date}")

    # if we use multi-pack index, take advantage of it
    if get_one_line_output([pbgit.get_git_executable(), "config", "core.multipackIndex"]) == "true":
        commands[0] += " --task incremental-repack"

    # fill in the git repo optionally
    is_shallow = get_one_line_output([pbgit.get_git_executable(), "rev-parse", "--is-shallow-repository"])

    # add in the front, so everything else can clean up after the fetch
    if is_shallow == "true":
        pblog.info("Shallow clone detected. PBSync will fill in history in the background.")
        commands.insert(0, f"{pbgit.get_git_executable()} fetch --unshallow")

    run_non_blocking(*commands)


def resolve_conflicts_and_pull(retry_count=0, max_retries=1):
    def should_attempt_auto_resolve():
        return retry_count <= max_retries

    if retry_count:
        # wait a little bit if retrying (exponential)
        time.sleep(0.25 * (1 << retry_count))

    out = get_combined_output([pbgit.get_git_executable(), "status", "--porcelain=2", "--branch"])

    if not it_has_any(out, "-0"):
        pbunreal.ensure_ue4_closed()
        pblog.info("Please wait while getting the latest changes from the repository. It may take a while...")
        # Make sure upstream is tracked correctly
        branch_name = pbgit.get_current_branch_name()
        pbgit.set_tracking_information(branch_name)
        pblog.info("Rebasing workspace with the latest changes from the repository...")
        # Get the latest files, but skip smudge so we can super charge a LFS pull as one batch
        result = run_with_combined_output([pbgit.get_git_executable(), "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=", "-c", "filter.lfs.required=false", "rebase", "--autostash", f"origin/{branch_name}"])
        # Pull LFS in one go since we skipped smudge (faster)
        run([pbgit.get_lfs_executable(), "pull"])
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
    elif "fast-forwarded" in out:
        handle_success()
    elif "up to date" in out:
        handle_success()
    elif "rewinding head" in out and not it_has_any(out, "error", "conflict"):
        handle_success()
    elif "successfully rebased and updated" in out:
        handle_success()
    elif it_has_any(out, "failed to merge in the changes", "could not apply"):
        handle_error("Aborting the rebase. Changes on one of your commits will be overridden by incoming changes. Please request help in #tech-support to resolve conflicts, and please do not run UpdateProject until the issue is resolved.")
    elif it_has_any(out, "unmerged files", "merge_head exists"):
        error_state("You are in the middle of a merge. Please request help in #tech-support to resolve it, and please do not run UpdateProject until the issue is resolved.", fatal_error=True)
    elif "unborn" in out:
        if should_attempt_auto_resolve():
            pblog.error("Unborn branch detected. Retrying...")
            retry_count += 1
            resolve_conflicts_and_pull(retry_count)
            return
        else:
            handle_error("You are on an unborn branch. Please request help in #tech-support to resolve it, and please do not run UpdateProject until the issue is resolved.")
    elif it_has_any(out, "no remote", "no such remote", "refspecs without repo"):
        if should_attempt_auto_resolve():
            pblog.error("Remote repository not found. Retrying...")
            retry_count += 1
            resolve_conflicts_and_pull(retry_count, 2)
            return
        else:
            handle_error("The remote repository could not be found. Please request help in #tech-support to resolve it, and please do not run UpdateProject until the issue is resolved.")
    elif "cannot open" in out:
        if should_attempt_auto_resolve():
            pblog.error("Git file info could not be read. Retrying...")
            retry_count += 1
            resolve_conflicts_and_pull(retry_count, 3)
            return
        else:
            handle_error("Git file info could not be read. Please request help in #tech-support to resolve it, and please do not run UpdateProject until the issue is resolved.")
    else:
        # We have no idea what the state of the repo is. Do nothing except bail.
        error_state("Aborting the repo update because of an unknown error. Request help in #tech-support to resolve it, and please do not run UpdateProject until the issue is resolved.", fatal_error=True)

    maintain_repo()
