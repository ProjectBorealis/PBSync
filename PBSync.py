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
pbsync_version = "0.0.2"
git_user_name = ""
expected_branch_name = "content-main"
git_hooks_path = "git-hooks"
shared_hooks_path = "Scripts\\HooksShared.bat"
############################################################################

### LOGGER
def LogSuccess(message, prefix = False):
    if prefix:
        print(Fore.GREEN + "SUCCESS: " + message + Style.RESET_ALL)
    else:
        print(Fore.GREEN + message + Style.RESET_ALL)

def LogWarning(message, prefix = True):
    if prefix:
        print(Fore.YELLOW + "WARNING: " + message + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + message + Style.RESET_ALL)

def LogError(message, prefix = True):
    if prefix:
        print(Fore.RED +  "ERROR: " + message + Style.RESET_ALL)
    else:
        print(Fore.RED + message + Style.RESET_ALL)
    print(Fore.RED + "Do not forget to take screenshot of the error log.\nPress Enter to quit..." + Style.RESET_ALL)
    input()
    sys.exit(1)
############################################################################

def CleanCache():
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

def CheckGitCredentials():
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

def SyncFile(file_path):
    return subprocess.call(["git", "checkout", "HEAD", "--", file_path])

def AbortMerge():
    subprocess.call(["git", "merge", "--abort"])

def SetupGitConfig():
    subprocess.call(["git", "config", "core.hooksPath", git_hooks_path])
    subprocess.call([shared_hooks_path])

def CheckoutTheirs(file_path):
    return subprocess.call(["git", "checkout", file_path, "--theirs"])

def CheckoutOurs(file_path):
    subprocess.call(["git", "checkout", file_path, "--ours"])
    return True

def GitAddFile(file_path):
    subprocess.call(["git", "add", file_path])

def RemoveFile(file_path):
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

def CheckCurrentBranchName():
    global expected_branch_name
    output = subprocess.getoutput(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    if output != expected_branch_name:
        LogWarning("Current branch is not set as " + expected_branch_name + ". Auto synchronization will be disabled")
        return False
    
    return True

def resolve_conflicts_and_pull():
    global git_user_name
    output = subprocess.getoutput(["git", "pull" "--rebase" "--autostash"])
    print(str(output))

    backup_folder = 'Backup/' + datetime.datetime.now().strftime("%I%M%Y%m%d")
    
    if "Automatic merge failed" in str(output):
        output = subprocess.getoutput(["git", "status", "--porcelain"])
        LogWarning("Conflicts found with your non-pushed commits. Another developer made changes on the files listed below, and pushed them into the repository before you:")
        print(output + "\n\n")
        du_file_list = [] # Deleted by us files
        ud_file_list = [] # Deleted by them files
        uu_file_list = [] # both modified files
        for file_path in output.splitlines():
            if file_path[0:2] == "DU":
                # File is deleted by us, but someone pushed a new commit for this file
                stripped_filename = file_path[3:]
                du_file_list.append(stripped_filename)
            elif file_path[0:2] == "UU":
                # Both modified
                stripped_filename = file_path[3:]
                uu_file_list.append(stripped_filename)
            elif file_path[0:2] == "UD":
                # File is deleted by them, but we did some work on this file
                stripped_filename = file_path[3:]
                ud_file_list.append(stripped_filename)

        AbortMerge()
        LogError("Aborting the merge. Please request help on #tech-support")
        return

    if "Aborting" in str(output):
        LogWarning("Conflicts found with uncommitted files in your workspace. Another developer made changes on the files listed below, and pushed them into the repository before you:")
        file_list = []
        for file_path in output.splitlines():
            if file_path[0] == '\t':
                stripped_filename = file_path.strip()
                file_list.append(stripped_filename)
                print(stripped_filename)

        LogWarning("You need to decide which files should be backed up", False)
       
        print("------------------\nGive an option as input to select actions per conflicted file:")
        for file_path in file_list:
            LogWarning("\nConflicted File: " + file_path)
            action = input("[1] Overwrite the file without backup\n[2] Overwrite the file with getting a backup of the current version\n[1/2 ?]: ")

            if int(action) == 2:
                file_backup_path = backup_folder + "/" + file_path[0:file_path.rfind("/")]
                try:
                    os.makedirs(file_backup_path)
                except:
                    # Probably the directory already exists error, pass
                    pass
                copy(file_path, file_backup_path)
                time.sleep(1)
                LogSuccess("Original file copied into: " + file_backup_path)
                LogSuccess("You can use this file if you want to restore your own version later")
            elif int(action) != 1:
                LogError("Incorrect option has given as input. Aborting...")
            
            if SyncFile(file_path) != 0:
                    LogWarning("Something went wrong while reverting the file. Trying to remove it from the workspace...")
                    if RemoveFile(file_path) == False:
                        LogError("Something went wrong while trying to resolve conflicts on " + file_path + ". Please request help on #tech-support")

            LogSuccess("Conflict resolved for " + file_path)
        
        LogSuccess("All conflicts are resolved. Trying to pull changes one more time...")
        status = subprocess.call(["git", "pull"])

        if status == 0:
            LogSuccess("\nSynchronization successful!")
        else:
            LogError("\nSomething went wrong while trying to pull new changes on repository. Please request help on #tech-support")
    else:
        LogSuccess("Pulled latest changes without any conflict", True)
                    

############################################################################

def main():
    parser = argparse.ArgumentParser(description="PBSync v" + pbsync_version)

    parser.add_argument("--syncengine", help="Synchronizes engine version to the latest one, versions are searched in the gcloud bucket URL given by the argument")
    parser.add_argument("--sync", help="Main command for the PBSync, synchronizes the project with latest changes in repo, and does some housekeeping")
    parser.add_argument("--latestenginever", help="Prints latest available engine version, versions are searched in the gcloud bucket URL given by the argument")
    args = parser.parse_args()

    # Process arguments
    if not (args.syncengine is None):
        engine_version = PBParser.GetLatestAvailableEngineVersion(str(args.syncengine))
        if engine_version is None:
            LogError("Error while trying to fetch latest engine version")
        if not PBParser.SetEngineVersion(engine_version):
            LogError("Error while trying to update engine version in .uproject file")
        LogSuccess("Successfully changed engine version as " + str(engine_version))
        sys.exit(0)

    elif not (args.latestenginever is None):
        engine_version = PBParser.GetLatestAvailableEngineVersion(str(args.latestenginever))
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end ="")
        sys.exit(0)

    elif not (args.sync is None):
        # Do Overall Project Synchronization for Creatives
        print("PBSync v" + pbsync_version + "\n\n")

        if PBTools.CheckGitInstallation() != 0:
            LogError("Git is not installed on the system. Please follow instructions in Gitlab wiki to prepare your workspace.")

        # Do not execute if Unreal Editor is running
        if PBTools.CheckRunningProcess("UE4Editor.exe"):
            LogError("Unreal Editor is running. Please close it before running PBSync")

        LogWarning("\nChecking for Git updates...", False)
        PBTools.CheckGitUpdate()

        # Do some housekeeping for git configuration
        SetupGitConfig()

        # Check if we have correct credentials
        CheckGitCredentials()

        print("\n------------------\n")

        project_version = PBParser.GetProjectVersion()
        engine_version = PBParser.GetSuffix()

        if project_version != "0.0.0":
            LogSuccess("Current project version: " + project_version)
        else:
            LogError("Something went wrong while fetching project version. Please request help on #tech-support")

        if engine_version != "":
            LogSuccess("Current engine build version: " + engine_version)
        else:
            LogError("Something went wrong while fetching engine build version. Please request help on #tech-support")

        print("\n------------------\n")

        LogWarning("Fetching recent changes on the repository...", False)
        if subprocess.call(["git", "fetch", "origin"]) != 0:
            LogError("Something went wrong while fetching changes on the repository. Please request help on #tech-support")

        LogWarning("\nChecking for engine updates...", False)
        if SyncFile("ProjectBorealis.uproject") != 0:
            LogError("Something went wrong while updating uproject file. Please request help on #tech-support")

        new_engine_version = PBParser.GetSuffix()

        if new_engine_version != engine_version:
            LogWarning("\nCustom engine will be updated from " + engine_version + " to " + new_engine_version)
            if PBTools.RunUe4Versionator() != 0:
                LogError("Something went wrong while updating engine build to " + new_engine_version + ". Please request help on #tech-support")
            else:
                LogSuccess("Custom engine successfully updated & registered as " + new_engine_version)
        else:
            LogSuccess("\nNo new engine builds found, trying to register current engine build...")
            if PBTools.RunUe4Versionator() != 0:
                LogError("Something went wrong while registering engine build " + new_engine_version + ". Please request help on #tech-support")
            else:
                LogSuccess("Engine build " + new_engine_version + " successfully registered")

        print("\n------------------\n")
        
        # Only execute synchronization part of script if we're on the expected branch
        if CheckCurrentBranchName():
            resolve_conflicts_and_pull()
            CleanCache()
            if PBTools.RunPBGet() != 0:
                LogError("An error occured while running PBGet. Please request help on #tech-support")

        os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")
        sys.exit(0)
    else:
        LogError("Please start PBSync from SyncProject.bat, or pass proper arguments to the executable!")
        

if __name__ == '__main__':
    colorama.init()
    main()