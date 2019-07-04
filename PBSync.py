import subprocess
import glob
import os.path
import os
import xml.etree.ElementTree as ET
import _winapi
import sys
import datetime
from shutil import copy
from shutil import rmtree

# PBSync Imports
import PBVersion
import PBTools

# Colored Output
import colorama
from colorama import Fore, Back, Style


### Globals
expected_branch_name = "content-main"
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

### Automation commands

def RunPBGet():
    os.chdir("PBGet")
    subprocess.call(["PBGet.exe", "resetcache"])
    status = subprocess.call(["PBGet.exe", "pull"])
    os.chdir("..")
    return status

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

def SyncFile(file_path):
    return subprocess.call(["git", "checkout", "HEAD", "--", file_path])

def AbortMerge():
    return subprocess.call(["git", "merge", "--abort"])

def CheckoutTheirs(file_path):
    return subprocess.call(["git", "checkout", file_path, "--theirs"])

def CheckoutOurs(file_path):
    return subprocess.call(["git", "checkout", file_path, "--ours"])

def RemoveFile(file_path):
    try:
        os.remove(file_path)
    except:
        LogWarning("Error while deleting file ", file_path)
        return False
    return not os.path.isfile(file_path)

def CheckCurrentBranchName():
    global expected_branch_name
    output = subprocess.getoutput(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    if output != expected_branch_name:
        LogError("Current branch is not set as " + expected_branch_name + ". Please request help on #tech-support")

def resolve_conflicts_and_pull():
    output = subprocess.getoutput(["git", "pull"])
    backup_folder = 'Backup/' + datetime.datetime.now().strftime("%I%M%Y%m%d")

    if "Automatic merge failed" in str(output):
        AbortMerge()
        LogWarning("Conflicts found with your non-pushed commits. Another developer made changes on the files listed below, and pushed them into the repository before you:")
        file_list = []
        for file_path in output.splitlines():
            if file_path[0] == '\t':
                stripped_filename = file_path.strip()
                file_list.append(stripped_filename)
                print(stripped_filename)
        LogError("Please do not forget to push your commits to avoid serious conflicts like this next time. You can request help on #tech-support to resolve conflicts")
        
        # TODO: A git lfs bug avoiding us to automatize conflict resolution:
        # "Encountered 1 file(s) that should have been pointers, but weren't" after rebase

        # LogWarning("You should decide what to do with conflicted files", False)
        # print("------------------\nGive an option as input to select actions per conflicted file")
        # modified_file_exists = False
        # for file_path in file_list:
        #     LogWarning("\nConflicted File: " + file_path)
        #     LogWarning("Keeping our version will also change the same file in the repository with ours after a successful push.")
        #     action = input("[1] Keep our version and reflect changes to repository\n[2] Keep incoming version and backup our file\n[1/2 ?]: ")

        #     if int(action) == 2:
        #         file_backup_path = backup_folder + "/" + file_path[0:file_path.rfind("/")]
        #         os.makedirs(file_backup_path)
        #         copy(file_path, file_backup_path)
        #         LogSuccess("Original file copied into: " + file_backup_path)
        #         LogSuccess("You can use this file if you want to restore your own version of the file later")

        #         LogSuccess("Updating the file to newest version...")
        #         if CheckoutTheirs(file_path) == 0:
        #             LogSuccess("Conflict resolved for " + file_path + " with their version of the file")
        #         else:
        #             AbortMerge()
        #             LogError("Something went wrong while trying to resolve conflicts on " + file_path + ". Aborting merge. Please request help on #tech-support")
            
        #     elif int(action) == 1:
        #         LogSuccess("Keeping our version of the file...")
        #         modified_file_exists = True
        #         if CheckoutOurs(file_path) == 0:
        #             LogSuccess("Conflict resolved for " + file_path + " with our version of the file.")
        #         else:
        #             AbortMerge()
        #             LogError("Something went wrong while trying to resolve conflicts on " + file_path + ". Aborting merge. Please request help on #tech-support")
            
        #     else:
        #         LogError("Incorrect option has given as input. Aborting...")

        # LogSuccess("All conflicts are resolved. Trying to add conflicted files...")
        # for file_path in file_list:
        #     if subprocess.call(["git", "add", file_path]) != 0:
        #         AbortMerge()
        #         LogError("Something went wrong while adding " + file_path + ". Aborting merge. Please request help on #tech-support")
        #     LogSuccess("Added " + file_path)
        
        # subprocess.call(["git", "merge", "--continue"])
        
        # if not modified_file_exists:
        #     subprocess.call(["git", "rebase"])
        # else:
        #     subprocess.call(["git", "push"])

        # LogSuccess("\nSynchronization successful!")
    elif "Aborting" in str(output):
        LogWarning("Conflicts found with uncommitted files in your workspace. Another developer made changes on the files listed below, and pushed them into the repository before you:")
        file_list = []
        for file_path in output.splitlines():
            if file_path[0] == '\t':
                stripped_filename = file_path.strip()
                file_list.append(stripped_filename)
                print(stripped_filename)

        LogWarning("You should decide which files should be backed up", False)
       
        print("------------------\nGive an option as input to select actions per conflicted file")
        for file_path in file_list:
            LogWarning("\nConflicted File: " + file_path)
            action = input("[1] Overwrite the file without backup\n[2] Overwrite the file with getting a backup of the current version\n[1/2 ?]: ")

            if int(action) == 2:
                file_backup_path = backup_folder + "/" + file_path[0:file_path.rfind("/")]
                os.makedirs(file_backup_path)
                copy(file_path, file_backup_path)
                LogSuccess("Original file copied into: " + file_backup_path)
                LogSuccess("You can use this file if you want to restore your own version of the file later")
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
    if PBTools.CheckGitInstallation() != 0:
        LogError("Git is not installed on the system. Please follow instructions in gitlab wiki to setup your workspace.")

    # Do not execute if we're not on the expected branch
    CheckCurrentBranchName()

    # Do not execute if Unreal Editor is running
    if PBTools.CheckRunningProcess("UE4Editor.exe"):
        LogError("Unreal Editor is running. Please close it before running PBSync")

    LogWarning("\nChecking for Git updates...", False)
    PBTools.CheckGitUpdate()

    print("\n------------------\n")

    project_version = PBVersion.GetProjectVersion()
    engine_version = PBVersion.GetSuffix()

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

    new_engine_version = PBVersion.GetSuffix()

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
    
    resolve_conflicts_and_pull()

    CleanCache()

    if RunPBGet() != 0:
        LogError("An error occured while running PBGet. Please request help on #tech-support")

    os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")
    sys.exit(0)
        

if __name__ == '__main__':
    colorama.init()
    main()