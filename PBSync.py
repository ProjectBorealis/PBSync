import subprocess
import glob
import os.path
import os
import xml.etree.ElementTree as ET
import _winapi
import time
import sys
import datetime
from shutil import copy
import errno, os, stat, shutil
from shutil import rmtree
import argparse

# PBSync Imports
import PBParser
import PBTools

# Colored Output
import colorama
from colorama import Fore, Back, Style

### Globals
pbsync_version = "0.0.4"
supported_git_version = "2.22"
supported_lfs_version = "2.8.0"

git_user_name = ""
expected_branch_name = "content-main"
git_hooks_path = "git-hooks"
shared_hooks_path = "Scripts\\HooksShared.bat"
############################################################################

### LOGGER
def log_success(message, prefix = False):
    if prefix:
        print(Fore.GREEN + "SUCCESS: " + message + Style.RESET_ALL)
    else:
        print(Fore.GREEN + message + Style.RESET_ALL)

def log_warning(message, prefix = True):
    if prefix:
        print(Fore.YELLOW + "WARNING: " + message + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + message + Style.RESET_ALL)

def log_error(message, prefix = True):
    rebase_switch(True)
    if prefix:
        print(Fore.RED +  "ERROR: " + message + Style.RESET_ALL)
    else:
        print(Fore.RED + message + Style.RESET_ALL)
    print(Fore.RED + "Do not forget to take screenshot of the error log.\nPress Enter to quit..." + Style.RESET_ALL)
    input()
    sys.exit(1)
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
    global git_user_name
    output = subprocess.getoutput(["git", "config", "user.name"])
    if output == "":
        user_name = input("Please enter your Gitlab username: ")
        subprocess.call(["git", "config", "--global", "user.name", user_name])
    else:
        git_user_name = output

    output = subprocess.getoutput(["git", "config", "user.email"])
    if output == "":
        user_mail = input("Please enter your Gitlab e-mail: ")
        subprocess.call(["git", "config", "--global", "user.email", user_mail])

def sync_file(file_path):
    return subprocess.call(["git", "checkout", "HEAD", "--", file_path])

def abort_merge():
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

def setup_git_config():
    subprocess.call(["git", "config", "core.hooksPath", git_hooks_path])
    subprocess.call([shared_hooks_path])

def checkout_theirs(file_path):
    return subprocess.call(["git", "checkout", file_path, "--theirs"])

def checkout_ours(file_path):
    subprocess.call(["git", "checkout", file_path, "--ours"])
    return True

def git_add_file(file_path):
    subprocess.call(["git", "add", file_path])

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

def check_current_branch_name():
    global expected_branch_name
    output = subprocess.getoutput(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    if output != expected_branch_name:
        log_warning("Current branch is not set as " + expected_branch_name + ". Auto synchronization will be disabled")
        return False
    
    return True

def resolve_conflicts_and_pull():
    global git_user_name

    # Abort if any merge or am request is going on at the moment
    abort_merge()

    # Turn off rebase pull & autostash for now
    rebase_switch(False)

    output = subprocess.getoutput(["git", "pull"])
    print(str(output))

    backup_folder = 'Backup/' + datetime.datetime.now().strftime("%I%M%Y%m%d")
    
    if 'Merge made by the \'recursive\' strategy' in str(output):
        if subprocess.call(["git", "rebase"]) != 0:
            abort_merge()
            log_error("Aborting the merge. You probably have unstaged changes in your workspace, and they're preventing your workspace to get synced. Please request help on #tech-support to solve problems in your workspace")

        if subprocess.call(["git", "push"]) != 0:
            abort_merge()
            log_error("Aborting the merge. Unable to push your non-pushed commits into origin. Please request help on #tech-support to solve problems in your workspace")

        log_success("\nSynchronization successful, and your previous commits are pushed into repository")

    if "Automatic merge failed" in str(output):
        output = subprocess.getoutput(["git", "status", "--porcelain"])
        log_warning("Conflicts found with your non-pushed commits. Another developer made changes on the files listed below, and pushed them into the repository before you:")
        print(output + "\n")

        abort_merge()
        log_error("Aborting the merge. Please request help on #tech-support to solve problems in your workspace")

    if "Please commit your changes or stash them before you merge" in str(output):
        log_warning("Conflicts found with uncommitted files in your workspace. Another developer made changes on the files listed below, and pushed them into the repository before you:")
        file_list = []
        for file_path in output.splitlines():
            if file_path[0] == '\t':
                stripped_filename = file_path.strip()
                file_list.append(stripped_filename)
                print(stripped_filename)

        for file_path in file_list:
            log_warning("\nYour conflicted File: " + file_path + " will backed up and overwritten by the changed version in the repository")

            file_backup_path = backup_folder + "/" + file_path[0:file_path.rfind("/")]
            try:
                os.makedirs(file_backup_path)
            except:
                # Probably the directory already exists error, pass
                pass
            copy(file_path, file_backup_path)
            time.sleep(1)
            log_success("Original file copied into: " + file_backup_path)
            log_success("You can use this file if you want to restore your own version later")
            
            if sync_file(file_path) != 0:
                log_warning("Something went wrong while reverting the file. Trying to remove it from the workspace...")
                if remove_file(file_path) == False:
                    log_error("Something went wrong while trying to resolve conflicts on " + file_path + ". Please request help on #tech-support")

            log_success("Conflict resolved for " + file_path)
        
        log_success("All conflicts are resolved. Trying to pull changes one more time...")
        status = subprocess.call(["git", "pull"])

        if status == 0:
            log_success("\nSynchronization successful!")
        else:
            log_error("\nSomething went wrong while trying to pull new changes on repository. Please request help on #tech-support")
    else:
        log_success("Pulled latest changes without any conflict", True)

    # Revert rebase config back
    rebase_switch(True)
############################################################################

def main():
    parser = argparse.ArgumentParser(description="PBSync v" + pbsync_version)

    parser.add_argument("--sync", help="[force-all, all, engine] Main command for the PBSync, synchronizes the project with latest changes in repo, and does some housekeeping")
    parser.add_argument("--print", help="[current-engine, latest-engine, project] Prints requested version information into console. latest-engine command needs --repository parameter")
    parser.add_argument("--repository", help="<URL> Required repository url for --print latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="[minor, major, release] Automatic version update for project version")
    args = parser.parse_args()

    # Process arguments
    if args.sync == "all" or args.sync == "force-all":
        print("Executing sync --all command for PBSync v" + pbsync_version + "\n")

        if not (supported_git_version in PBTools.check_git_installation()):
            log_error("Git is not installed in your system or it's not updated to the latest version " + supported_git_version + ". Please install/update Git.")
        else:
            log_success("Current Git version: " + supported_git_version)

        if not (supported_lfs_version in PBTools.check_lfs_installation()):
            log_error("Git LFS is not installed in your system or it's not updated to the latest version " + supported_lfs_version + ". Please install/update Git LFS.")
        else:
            log_success("Current Git LFS version: " + supported_lfs_version)

        # Do not execute if Unreal Editor is running
        if PBTools.check_running_process("UE4Editor.exe"):
            log_error("Unreal Editor is running. Please close it before running PBSync")

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
            log_success("Current engine build version: " + engine_version)
        else:
            log_error("Something went wrong while fetching engine build version. Please request help on #tech-support")

        print("\n------------------\n")

        log_warning("Fetching recent changes on the repository...", False)
        if subprocess.call(["git", "fetch", "origin"]) != 0:
            log_error("Something went wrong while fetching changes on the repository. Please request help on #tech-support")

        log_warning("\nChecking for engine updates...", False)
        if sync_file("ProjectBorealis.uproject") != 0:
            log_error("Something went wrong while updating uproject file. Please request help on #tech-support")

        new_engine_version =  PBParser.get_engine_version()

        if new_engine_version != engine_version:
            log_warning("\nCustom engine will be updated from " + engine_version + " to " + new_engine_version)
            if PBTools.run_ue4versionator() != 0:
                log_error("Something went wrong while updating engine build to " + new_engine_version + ". Please request help on #tech-support")
            else:
                log_success("Custom engine successfully updated & registered as " + new_engine_version)
        else:
            log_success("\nNo new engine builds found, trying to register current engine build...")
            if PBTools.run_ue4versionator() != 0:
                log_error("Something went wrong while registering engine build " + new_engine_version + ". Please request help on #tech-support")
            else:
                log_success("Engine build " + new_engine_version + " successfully registered")

        print("\n------------------\n")
        
        # Only execute synchronization part of script if we're on the expected branch
        if check_current_branch_name() or args.sync == "force-all":
            resolve_conflicts_and_pull()
            clean_cache()
            if PBTools.run_pbget() != 0:
                log_error("An error occured while running PBGet. Please request help on #tech-support")

        os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")
        sys.exit(0)

    elif args.sync == "engine":
        if args.repository is None:
            log_error("--repository <URL> argument should be provided with --sync engine command")
        engine_version = PBParser.get_latest_available_engine_version(str(args.repository))
        if engine_version is None:
            log_error("Error while trying to fetch latest engine version")
        if not PBParser.set_engine_version(engine_version):
            log_error("Error while trying to update engine version in .uproject file")
        log_success("Successfully changed engine version as " + str(engine_version))
        sys.exit(0)

    elif args.print == "latest-engine":
        if args.repository is None:
            log_error("--repository <URL> argument should be provided with --print latest-engine command")
        engine_version = PBParser.get_latest_available_engine_version(str(args.repository))
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end ="")
        sys.exit(0)
    
    elif args.print == "current-engine":
        engine_version = PBParser.get_engine_version()
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end ="")
        sys.exit(0)
    
    elif args.print == "project":
        project_version = PBParser.get_project_version()
        if project_version is None:
            sys.exit(1)
        print(project_version, end ="")
        sys.exit(0)
    
    elif not (args.autoversion is None):
        if PBParser.project_version_increase(args.autoversion):
            log_success("Successfully increased project version")
        else:
            log_error("Error occured while trying to increase project version")
        sys.exit(0)

    else:
        log_error("Please start PBSync from SyncProject.bat, or pass proper argument set to the executable")
        

if __name__ == '__main__':
    colorama.init()
    main()