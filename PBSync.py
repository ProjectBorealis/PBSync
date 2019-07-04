import subprocess
import glob
import os.path
import os
import xml.etree.ElementTree as ET
import _winapi
import sys
import datetime
from shutil import copy

# PBSync Imports
import PBVersion
import PBTools

# Colored Output
import colorama
from colorama import Fore, Back, Style


### Globals
error_state = 0
warning_state = 0
############################################################################

### LOGGER
def LogSuccess(message, prefix = False):
    if prefix:
        print(Fore.GREEN + "SUCCESS: " + message + Style.RESET_ALL)
    else:
        print(Fore.GREEN + message + Style.RESET_ALL)

def LogWarning(message, prefix = True):
    global warning_state
    warning_state = 1
    if prefix:
        print(Fore.YELLOW + "WARNING: " + message + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + message + Style.RESET_ALL)

def LogError(message, prefix = True):
    global error_state
    error_state = 1
    if prefix:
        print(Fore.RED +  "ERROR: " + message + Style.RESET_ALL)
    else:
        print(Fore.RED + message + Style.RESET_ALL)
############################################################################

def SyncFile(file_path):
    return subprocess.call(["git", "checkout", "HEAD", "--", file_path])

def RemoveFile(file_path):
    os.remove(file_path)
    return 0

### Automation commands
def ResolvePossibleConflicts():
    output = subprocess.getoutput(["git", "pull"])

    if "Aborting" not in str(output):
        LogSuccess("Successfully pulled latest changes!")
        return True
    else:
        LogWarning("Conflicts found in your current workspace. Someone else also made changes, and pushed those files to the repository.")
        LogWarning("You need to decide that if you want to overwrite your files with incoming ones, or keep incoming files and backup your current files.", False)
       
        print("------------------\n Give 1 or 2 as input to select actions per conflicted file")
        backup_folder = 'Backup/' + datetime.datetime.now().strftime("%I%M%Y%m%d")
        for file_path in output.splitlines():
            if file_path[0] == '\t':
                file_path = file_path.strip()
                print("\nConflicted File: " + file_path)
                action = input("[1] Overwrite the file with new version, and lose changes\n[2] Overwrite the file with new version, and backup your own version\n[1/2 ?]: ")

                if int(action) == 2:
                    file_backup_path = backup_folder + "/" + file_path[0:file_path.rfind("/")]
                    os.makedirs(file_backup_path)
                    copy(file_path, file_backup_path)
                    print("Backup completed on: " + file_backup_path)
                
                if SyncFile(file_path) != 0:
                        LogWarning("Unable to checkout this file. Trying to remove...")
                        if RemoveFile(file_path) != 0:
                            LogError("Something went wrong while trying to resolve conflicts on " + file_path + ". Please request help on #tech-support")
                            sys.exit(1)

                print("Conflict resolved for " + file_path)
        
        status = subprocess.call(["git", "pull"])

        if status == 0:
            print("Synchronization successful!")
        else:
            LogError("Something went wrong while trying to pull new  changes on repository. Please request help on #tech-support")
            sys.exit(1)
                    

############################################################################

def main():
    # TODO: Do not let programmers run this exe
    # TODO: Do not run if unreal is running

    # if PBTools.CheckGitInstallation() != 0:
    #     LogError("Git is not installed on the system. Please follow instructions in gitlab wiki to setup your workspace.")
    #     sys.exit(1)
    
    # print("\nChecking for Git updates...")
    # PBTools.CheckGitUpdate()

    # project_version = PBVersion.GetProjectVersion()
    # engine_version = PBVersion.GetSuffix()

    # if project_version != "0.0.0":
    #     LogSuccess("\nWorkspace project version: " + project_version)
    # else:
    #     LogError("Something went wrong while fetching project version. Please request help on #tech-support")
    #     sys.exit(1)

    # if engine_version != "":
    #     LogSuccess("\nWorkspace engine build version: " + engine_version)
    # else:
    #     LogError("Something went wrong while fetching engine build version. Please request help on #tech-support")
    #     sys.exit(1)

    # LogSuccess("\nFetching recent changes on the repository...")
    # if subprocess.call(["git", "fetch", "origin"]) != 0:
    #     LogError("Something went wrong while fetching changes on the repository. Please request help on #tech-support")

    # LogSuccess("\nChecking for engine updates...")
    # if SyncFile("ProjectBorealis.uproject") != 0:
    #     LogError("Something went wrong while updating uproject file. Please request help on #tech-support")

    # new_engine_version = PBVersion.GetSuffix()

    # if new_engine_version != engine_version:
    #     LogSuccess("\nUnreal Engine will be updated from " + engine_version + " to " + new_engine_version)
    #     if PBTools.RunUe4Versionator() != 0:
    #         LogError("Something went wrong while updating Unreal Engine. Please request help on #tech-support")
    #     else:
    #         LogSuccess("Unreal Engine successfully updated to " + new_engine_version)
    # else:
    #     LogSuccess("\nNo new engine builds found, trying to register current engine build...")
    #     if PBTools.RunUe4Versionator() != 0:
    #         LogError("Something went wrong while registering Unreal Engine to project. Please request help on #tech-support")
    #     else:
    #         LogSuccess("Unreal Engine successfully registered for the project")
    
    ResolvePossibleConflicts()

if __name__ == '__main__':
    colorama.init()
    main()