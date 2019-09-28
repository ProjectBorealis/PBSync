import subprocess
import os.path
import os
import time
import sys
import datetime
from shutil import copy
import stat
from shutil import rmtree
import argparse

# PBSync Imports
import PBParser
import PBTools

# Colored Output
import colorama
from colorama import Fore, Back, Style

### Globals
pbsync_version = "0.0.10"
supported_git_version = "2.23.0"
supported_lfs_version = "2.8.0"
engine_base_version = "4.23"

expected_branch_name = "content-main"
git_hooks_path = "git-hooks"
watchman_executable_name = "watchman.exe"
############################################################################

### LOGGER
def log_success(msg, prefix = False):
    if prefix:
        print(Fore.GREEN + "SUCCESS: " + msg + Style.RESET_ALL)
    else:
        print(Fore.GREEN + msg + Style.RESET_ALL)

def log_warning(msg, prefix = True):
    if prefix:
        print(Fore.YELLOW + "WARNING: " + msg + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + msg + Style.RESET_ALL)

def log_error(msg, prefix = True):
    rebase_switch(True)
    if prefix:
        print(Fore.RED +  "ERROR: " + msg + Style.RESET_ALL)
    else:
        print(Fore.RED + msg + Style.RESET_ALL)
    stop_transcript()
    print(Fore.RED + "Error logs are recorded in pbsync_log.txt file.\nPress Enter to quit..." + Style.RESET_ALL)
    input()
    sys.exit(1) 

class Transcript(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.logfile = open(filename, "w")

    def write(self, message):
        self.terminal.write(message)
        self.logfile.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        # you might want to specify some extra behavior here.
        pass

def stop_transcript():
    if hasattr(sys.stdout, "logfile"):
        sys.stdout.logfile.close()
        sys.stdout = sys.stdout.terminal

def start_transcript(filename):
    sys.stdout = Transcript(filename)
############################################################################

def clean_cache():
    cache_dir = ".git\\lfs\\cache"
    if os.path.isdir(cache_dir):
        try:
            rmtree(cache_dir)
        except:
            pass
        
    lockcache_path = ".git\\lfs\\lockcache.db"
    if os.path.isfile(lockcache_path):
        try:
            os.remove(lockcache_path)
        except:
            pass

def check_git_credentials():
    output = str(subprocess.getoutput(["git", "config", "user.name"]))
    if output == "" or output == None:
        user_name = input("Please enter your Gitlab username: ")
        subprocess.call(["git", "config", "user.name", user_name])

    output = str(subprocess.getoutput(["git", "config", "user.email"]))
    if output == "" or output == None:
        user_mail = input("Please enter your Gitlab e-mail: ")
        subprocess.call(["git", "config", "user.email", user_mail])

def sync_file(file_path):
    sync_head = "origin/" + get_current_branch_name()
    return subprocess.call(["git", "checkout", sync_head, "--", file_path])

def abort_merge():
    # Abort everything
    out = subprocess.getoutput(["git", "merge", "--abort"])
    out = subprocess.getoutput(["git", "rebase", "--abort"])
    out = subprocess.getoutput(["git", "am", "--abort"])

def rebase_switch(switch_val):
    if switch_val:
        subprocess.call(["git", "config", "pull.rebase", "true"])
        subprocess.call(["git", "config", "rebase.autoStash", "true"])
    else:
        subprocess.call(["git", "config", "pull.rebase", "false"])
        subprocess.call(["git", "config", "rebase.autoStash", "false"])

def disable_watchman():
    subprocess.call(["git", "config", "--unset", "core.fsmonitor"])
    if PBTools.check_running_process(watchman_executable_name):
        os.system("taskkill /f /im " + watchman_executable_name)

def enable_watchman():
    subprocess.call(["git", "config", "core.fsmonitor", "git-watchman/query-watchman"])
    # Trigger
    out = subprocess.getoutput(["git", "status"])

def wipe_workspace():
    current_branch = get_current_branch_name()
    response = input("This command will wipe your workspace and get latest changes from " + current_branch + ". Are you sure? [y/N]")
    
    if response != "y" and response != "Y":
        return False

    abort_merge()
    rebase_switch(False)
    disable_watchman()
    subprocess.call(["git", "fetch", "origin", str(current_branch)])
    result = subprocess.call(["git", "reset", "--hard", "FETCH_HEAD"])
    subprocess.call(["git", "clean", "-fd"])
    enable_watchman()
    rebase_switch(True)
    return result == 0

def setup_git_config():
    # Keep those files always in sync with origin
    sync_file(git_hooks_path)
    subprocess.call(["git", "config", "core.hooksPath", git_hooks_path])
    subprocess.call(["git", "config", "core.autocrlf", "true"])
    subprocess.call(["git", "config", "help.autocorrect", "true"])
    subprocess.call(["git", "config", "commit.template", "git-hooks/gitmessage.txt"])
    subprocess.call(["git", "config", "merge.conflictstyle", "diff3"])
    subprocess.call(["git", "config", "push.default", "current"])
    # subprocess.call(["git", "show-ref", "-s", "|", "git", "commit-graph write", "--stdin-commits"]) # Broken in git 2.23

def remove_file(file_path):
    try:
        os.remove(file_path)
    except:
        os.chmod(file_path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
        try:
            os.remove(file_path)
        except Exception as e:
            print(e)
            pass
    return not os.path.isfile(file_path)

def get_current_branch_name():
    return str(subprocess.getoutput(["git", "branch", "--show-current"]))

def check_current_branch_name():
    global expected_branch_name
    # "git branch --show-current" is a new feature in git 2.22
    output = get_current_branch_name()

    if output != expected_branch_name:
        log_warning("Current branch is not set as " + expected_branch_name + ". Auto synchronization will be disabled")
        return False
    
    # In any case, always set upstream to track same branch
    subprocess.call(["git", "branch", "--set-upstream-to=origin/" + str(output), str(output)])

    return True

def resolve_conflicts_and_pull():
    # Abort if any merge, rebase or am request is going on at the moment
    abort_merge()

    # Turn off rebase pull & autostash for now
    rebase_switch(False)
    
    # Disable watchman for now
    disable_watchman()

    output = subprocess.getoutput(["git", "status"])

    log_success("Please wait while getting latest changes on the repository. It may take a while...")

    if "Your branch is ahead of" in str(output):
        abort_merge()
        log_error("You have non-pushed commits. Please push them first to process further. If you're not sure about how to do that, request help from #tech-support")

    elif "nothing to commit, working tree clean" in str(output):
        log_success("Resetting your local workspace to latest FETCH_HEAD...")
        curr_branch_name = get_current_branch_name()
        subprocess.call("git", "fetch", "origin", curr_branch_name)
        subprocess.call("git", "reset", "--hard", "FETCH_HEAD")
        log_success("Pulled changes without any conflict", True)

    else:
        output = subprocess.getoutput(["git", "pull"])
        print(str(output))

        backup_folder = 'Backup/' + datetime.datetime.now().strftime("%I%M%Y%m%d")
        
        if "There is no tracking information for the current branch" in str(output):
            abort_merge()
            log_error("Aborting the merge. Your local branch is not tracked by remote anymore. Please request help on #tech-support to solve the problem")

        elif "Please commit your changes or stash them before you merge" in str(output):
            log_warning("Conflicts found with uncommitted files in your workspace. Another developer made changes on the files listed below, and pushed them into the repository before you:")
            file_list = []
            for file_path in output.splitlines():
                if file_path[0] == '\t':
                    stripped_filename = file_path.strip()
                    file_list.append(stripped_filename)
                    print(stripped_filename)
            
            response = input("Files listed above will be overwritten by incoming versions from repository and your work will be backed up in Backup folder. Do you want to continue? [y/N]")
            if(response != "y" and response != "Y"):
                log_error("Please request help on #tech-support to resolve your conflicts")

            for file_path in file_list:
                file_backup_path = backup_folder + "/" + file_path[0:file_path.rfind("/")]
                try:
                    os.makedirs(file_backup_path)
                except:
                    # Probably the directory already exists error, pass
                    pass
                copy(file_path, file_backup_path)
                time.sleep(1)

                if sync_file(file_path) != 0:
                    log_warning("Something went wrong while reverting the file. Trying to remove it from the workspace...")
                    if remove_file(file_path) == False:
                        log_error("Something went wrong while trying to resolve conflicts on " + file_path + ". Please request help on #tech-support")

                log_success("Conflict resolved for " + file_path)
                log_success("File backed up in " + file_backup_path)
            
            log_success("All conflicts are resolved. Trying to pull changes one more time...")
            status = subprocess.call(["git", "pull"])

            if status == 0:
                log_success("\nSynchronization successful!")
            else:
                log_error("\nSomething went wrong while trying to pull new changes on repository. Please request help on #tech-support")
        
        elif "The following untracked working tree files would be overwritten by merge" in str(output):
            file_list = []
            for file_path in output.splitlines():
                if file_path[0] == '\t':
                    stripped_filename = file_path.strip()
                    file_list.append(stripped_filename)
                    print(stripped_filename)
            
            response = input("Untracked files listed above will be overwritten with new versions, do you confirm? (This can't be reverted) [y/N] ")

            if response == "y" or response == "Y":
                for file_path in file_list:
                    remove_file(file_path)
                    log_warning("Removed untracked file: " + str(file_path))
                log_success("Running synchronization command again...")
                # Run the whole function again, we have resolved the overwritten untracked file problem
                resolve_conflicts_and_pull()
                return
            else:
                log_error("Aborting...")
                abort_merge()
                log_error("\nSomething went wrong while trying to pull new changes on repository. Please request help on #tech-support")
        elif "Aborting" in str(output):
            log_error("\nSomething went wrong while trying to pull new changes on repository. Please request help on #tech-support")
        else:
            log_success("Pulled latest changes without any conflict", True)

    # Revert rebase config back
    rebase_switch(True)
############################################################################

def main():
    parser = argparse.ArgumentParser(description="PBSync v" + pbsync_version)

    parser.add_argument("--sync", help="[force, all, engine] Main command for the PBSync, synchronizes the project with latest changes in repo, and does some housekeeping")
    parser.add_argument("--print", help="[current-engine, latest-engine, project] Prints requested version information into console. latest-engine command needs --repository parameter")
    parser.add_argument("--repository", help="<URL> Required repository url for --print latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="[minor, major, release] Automatic version update for project version")
    parser.add_argument("--wipe", help="[latest] Wipe the workspace and get latest changes from current branch (Not revertable)")
    args = parser.parse_args()

    # Process arguments
    if args.sync == "all" or args.sync == "force":
        start_transcript("pbsync_log.txt")
        print("Executing " + str(args.sync) + " sync command for PBSync v" + pbsync_version + "\n")
        
        print("\n------------------\n")

        git_version_result = PBParser.compare_git_version(supported_git_version)
        if git_version_result == -2:
            # Handle parse error first, in case of possibility of getting expection in following get_git_version() calls
            log_error("Git is not installed correctly on your system. \n"+
                "Please install latest Git from https://git-scm.com/download/win")
        elif git_version_result == 0:
            log_success("Current Git version: " + PBParser.get_git_version())
        elif git_version_result == -1:
            log_error("Git is not updated to the latest version in your system\n" +
                "Supported Git Version: " + supported_git_version + "\n" +
                "Current Git Version: " + PBParser.get_git_version() + "\n" +
                "Please install latest Git from https://git-scm.com/download/win")
        elif git_version_result == 1:
            log_warning("Current Git version is newer than supported one: " + PBParser.get_git_version())
            log_warning("Supported Git version: " + supported_git_version)
        else:
            log_error("Git is not installed correctly on your system. \n"+
                "Please install latest Git from https://git-scm.com/download/win")

        lfs_version_result = PBParser.compare_lfs_version(supported_lfs_version)
        if lfs_version_result == -2:
            # Handle parse error first, in case of possibility of getting expection in following get_git_version() calls
            log_error("Git LFS is not installed correctly on your system. \n"+
                "Please install latest Git LFS from https://git-lfs.github.com")
        elif lfs_version_result == 0:
            log_success("Current Git LFS version: " + PBParser.get_lfs_version())
        elif lfs_version_result == -1:
            log_error("Git LFS is not updated to the latest version in your system\n" +
                "Supported Git LFS Version: " + supported_lfs_version + "\n" +
                "Current Git LFS Version: " + PBParser.get_lfs_version() + "\n" +
                "Please install latest Git LFS from https://git-lfs.github.com")
        elif lfs_version_result == 1:
            log_warning("Current Git LFS version is newer than supported one: " + PBParser.get_lfs_version())
            log_warning("Supported Git LFS version: " + supported_lfs_version)
        else:
            log_error("Git LFS is not installed correctly on your system. \n"+
                "Please install latest Git LFS from https://git-lfs.github.com")

        print("\n------------------\n")

        # Do not execute if Unreal Editor is running
        if PBTools.check_running_process("UE4Editor.exe"):
            log_error("Unreal Editor is currently running. Please close it before running PBSync")

        log_warning("Fetching recent changes on the repository...", False)
        subprocess.call(["git", "fetch", "origin"])

        # Do some housekeeping for git configuration
        setup_git_config()

        # Check if we have correct credentials
        check_git_credentials()

        print("\n------------------\n")

        project_version = PBParser.get_project_version()

        if project_version != None:
            log_success("Current project version: " + project_version)
        else:
            log_error("Something went wrong while fetching project version. Please request help on #tech-support")
        
        engine_version = PBParser.get_engine_version()

        if engine_version != None:
            log_success("Current engine build version: " + engine_base_version + "-PB-" + engine_version)
        else:
            log_error("Something went wrong while fetching engine build version. Please request help on #tech-support")

        print("\n------------------\n")

        log_warning("\nChecking for engine updates...", False)
        if sync_file("ProjectBorealis.uproject") != 0:
            log_error("Something went wrong while updating .uproject file. Please request help on #tech-support")

        new_engine_version =  PBParser.get_engine_version()

        if new_engine_version != engine_version:
            log_warning("\nCustom engine will be updated from " + engine_version + " to " + new_engine_version)
            if PBTools.run_ue4versionator() != 0:
                log_error("Something went wrong while updating engine build to " + new_engine_version + ". Please request help on #tech-support")
            else:
                log_success("Custom engine successfully updated & registered as " + new_engine_version)
        else:
            log_success("\nTrying to register current engine build if it exists. Otherwise, required build will be downloaded...")
            if PBTools.run_ue4versionator() != 0:
                log_error("Something went wrong while registering engine build " + new_engine_version + ". Please request help on #tech-support")
            else:
                log_success("Engine build " + new_engine_version + " successfully registered")

        print("\n------------------\n")
        
        # Execute synchronization part of script if we're on the expected branch, force sync is enabled
        if args.sync == "force" or check_current_branch_name():
            resolve_conflicts_and_pull()
            print("\n------------------\n")
            clean_cache()
            if PBTools.run_pbget() != 0:
                log_error("An error occured while running PBGet. It's likely binary files for this release are not pushed yet. Please request help on #tech-support")
        
        # Run watchman in any case it's disabled
        enable_watchman()

        stop_transcript()
        os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")

    elif args.sync == "engine":
        if args.repository is None:
            log_error("--repository <URL> argument should be provided with --sync engine command")
        engine_version = PBParser.get_latest_available_engine_version(str(args.repository))
        if engine_version is None:
            log_error("Error while trying to fetch latest engine version")
        if not PBParser.set_engine_version(engine_version):
            log_error("Error while trying to update engine version in .uproject file")
        log_success("Successfully changed engine version as " + str(engine_version))

    elif args.print == "latest-engine":
        if args.repository is None:
            log_error("--repository <URL> argument should be provided with --print latest-engine command")
        engine_version = PBParser.get_latest_available_engine_version(str(args.repository))
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end ="")
    
    elif args.print == "current-engine":
        engine_version = PBParser.get_engine_version()
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end ="")
    
    elif args.print == "project":
        project_version = PBParser.get_project_version()
        if project_version is None:
            sys.exit(1)
        print(project_version, end ="")
    
    elif not (args.autoversion is None):
        if PBParser.project_version_increase(args.autoversion):
            log_success("Successfully increased project version")
        else:
            log_error("Error occured while trying to increase project version")

    elif not (args.wipe is None):
        if wipe_workspace():
            log_success("Workspace wipe successful")
            input("Press enter to quit...")
        else:
            log_error("Something went wrong while wiping the workspace")

    else:
        log_error("Please start PBSync from StartProject.bat, or pass proper argument set to the executable")
        

if __name__ == '__main__':
    if "Scripts" in os.getcwd():
        # Exception for scripts running PBSync from Scripts folder
        os.chdir("..")

    colorama.init()
    main()
    stop_transcript()
