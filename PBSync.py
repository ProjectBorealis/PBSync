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
import logging

# PBSync Imports
import PBParser
import PBTools
import PBConfig

def error_state(fatal_error = False):
    if fatal_error:
        # That was a fatal error, until issue is fixed, do not let user run PBSync
        PBParser.pbsync_error_state(True)
    out = input("Logs are saved in " + PBConfig.get("log_file_path") + ". Press enter to quit...")
    sys.exit(1)

def git_stash_pop():
    logging.info("Trying to pop stash...")

    output = subprocess.getoutput(["git", "stash", "pop"])
    logging.info(str(output))

    lower_case_output = str(output).lower()

    if "auto-merging" in lower_case_output and "conflict" in lower_case_output and "should have been pointers" in lower_case_output:
        logging.error("Git stash pop is failed. Some of your stashed local changes would be overwritten by incoming changes. Request help on #tech-support to resolve conflicts, and  please do not run StartProject.bat until issue is solved.")
        error_state(True)
    elif "dropped refs" in lower_case_output:
        return
    elif "no stash entries found" in lower_case_output:
        return
    else:
        logging.error("Git stash pop is failed due to unknown error. Request help on #tech-support to resolve possible conflicts, and  please do not run StartProject.bat until issue is solved.")
        error_state(True)

def check_git_credentials():
    output = str(subprocess.getoutput(["git", "config", "user.name"]))
    if output == "" or output == None:
        user_name = input("Please enter your Github username: ")
        subprocess.call(["git", "config", "user.name", user_name])

    output = str(subprocess.getoutput(["git", "config", "user.email"]))
    if output == "" or output == None:
        user_mail = input("Please enter your Github e-mail: ")
        subprocess.call(["git", "config", "user.email", user_mail])

def sync_file(file_path):
    sync_head = "origin/" + get_current_branch_name()
    return subprocess.call(["git", "checkout", "-f", sync_head, "--", file_path])

def abort_all():
    # Abort everything
    out = subprocess.getoutput(["git", "merge", "--abort"])
    out = subprocess.getoutput(["git", "rebase", "--abort"])
    out = subprocess.getoutput(["git", "am", "--abort"])

def abort_rebase():
    # Abort rebase
    out = subprocess.getoutput(["git", "rebase", "--abort"])

def disable_watchman():
    subprocess.call(["git", "config", "--unset", "core.fsmonitor"])
    if PBTools.check_running_process(PBConfig.get('watchman_executable_name')):
        os.system("taskkill /f /im " + PBConfig.get('watchman_executable_name'))

def enable_watchman():
    subprocess.call(["git", "config", "core.fsmonitor", "git-watchman/query-watchman"])
    # Trigger
    out = subprocess.getoutput(["git", "status"])

def wipe_workspace():
    current_branch = get_current_branch_name()
    response = input("This command will wipe your workspace and get latest changes from " + current_branch + ". Are you sure? [y/N]")
    
    if response != "y" and response != "Y":
        return False

    abort_all()
    disable_watchman()
    subprocess.call(["git", "fetch", "origin", str(current_branch)])
    result = subprocess.call(["git", "reset", "--hard", "origin/" + str(current_branch)])
    subprocess.call(["git", "clean", "-fd"])
    subprocess.call(["git", "pull"])
    enable_watchman()
    return result == 0

def setup_git_config():
    subprocess.call(["git", "config", PBConfig.get('lfs_lock_url'), "true"])
    subprocess.call(["git", "config", "core.hooksPath", PBConfig.get('git_hooks_path')])
    subprocess.call(["git", "config", "include.path", '"$PWD/.gitconfig"'])

def generate_ddc_command():
    logging.info("Generating DDC data, please wait... (This may take up to one hour only for the initial run)")
    state, err = PBTools.generate_ddc_data()
    logging.info("DDC generate command has exited with " + str(err))
    if state == 0:
        logging.info("DDC data successfully generated & versioned!")
    elif state == 1:
        logging.error("Error occured while trying to read project version for DDC data generation. Please get support from #tech-support")
        error_state()
    elif state == 2:
        logging.error("Generated DDC data was smaller than expected. Please get support from #tech-support")
        error_state()
    else:
        logging.error("Unspecified error occured while generating DDC data. Please get support from #tech-support")
        error_state()

def remove_file(file_path):
    try:
        os.remove(file_path)
    except:
        os.chmod(file_path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
        try:
            os.remove(file_path)
        except Exception as e:
            logging.exception(str(e))
            pass
    return not os.path.isfile(file_path)

def get_current_branch_name():
    return str(subprocess.getoutput(["git", "branch", "--show-current"]))

def is_expected_branch():
    output = get_current_branch_name()
    
    if output != PBConfig.get('expected_branch_name'):
        return False

    # In any case, always set upstream to track same branch (only if we're on expected branch)
    out = subprocess.getoutput(["git", "branch", "--set-upstream-to=origin/" + str(output), str(output)])
    return True

def resolve_conflicts_and_pull():
    # Disable watchman for now
    disable_watchman()

    output = subprocess.getoutput(["git", "status"])
    logging.info(str(output))

    logging.info("Please wait while getting latest changes on the repository. It may take a while...")

    logging.info("Trying to stash the local work...")
    output = subprocess.getoutput(["git", "stash"])
    logging.info(str(output))

    logging.info("Trying to rebase workspace with latest changes on the repository...")
    output = subprocess.getoutput(["git", "pull", "--rebase"])
    logging.info(str(output))

    lower_case_output = str(output).lower()

    if "failed to merge in the changes" in lower_case_output or "could not apply" in lower_case_output:
        logging.error("Aborting the rebase. Changes on one of your commits will be overridden by incoming changes. Request help on #tech-support to resolve conflicts, and  please do not run StartProject.bat until issue is solved.")
        abort_rebase()
        git_stash_pop()
        error_state(True)
    elif "fast-forwarded" in lower_case_output:
        git_stash_pop()
        logging.info("Success, rebased on latest changes without any conflict")
    elif "is up to date" in lower_case_output:
        git_stash_pop()
        logging.info("Success, rebased on latest changes without any conflict")
    elif "rewinding head" in lower_case_output and not("error" in lower_case_output or "conflict" in lower_case_output):
        git_stash_pop()
        logging.info("Success, rebased on latest changes without any conflict")
    else:
        logging.error("Aborting the rebase, an unknown error occured. Request help on #tech-support to resolve conflicts, and please do not run StartProject.bat until issue is solved.")
        abort_rebase()
        git_stash_pop()
        error_state(True)

    # Run watchman back
    enable_watchman()
############################################################################

def main():
    parser = argparse.ArgumentParser(description="Project Borealis Workspace Synchronization Tool")

    parser.add_argument("--sync", help="[force, all, engine, ddc] Main command for the PBSync, synchronizes the project with latest changes in repo, and does some housekeeping")
    parser.add_argument("--print", help="[current-engine, latest-engine, project] Prints requested version information into console. latest-engine command needs --repository parameter")
    parser.add_argument("--repository", help="<URL> Required repository url for --print latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="[hotfix, stable, public] Automatic version update for project version")
    parser.add_argument("--wipe", help="[latest] Wipe the workspace and get latest changes from current branch (Not revertable)")
    parser.add_argument("--clean", help="[engine] Do cleanup according to specified argument")
    parser.add_argument("--config", help="Path of config XML file. If not provided, ./PBSync.xml is used as default")
    parser.add_argument("--push", help="[apikey] Push current binaries into NuGet repository with provided api key. If provided with --autoversion, push will be done after auto versioning.")
    parser.add_argument("--publish", help="[stable, public] Publishes a playable build with provided build type")
    args = parser.parse_args()

    # If config parameter is not passed, default to PBSync.xml
    if args.config == None:
        args.config = "PBSync.xml"

    if PBConfig.generate_config(args.config):
        # If log file is big enough, remove it
        if os.path.isfile(PBConfig.get('log_file_path')) and os.path.getsize(PBConfig.get('log_file_path')) >= PBConfig.get('max_log_size'):
            remove_file(PBConfig.get('log_file_path'))

        # Setup logger
        logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s", datefmt='%d-%b-%y %H:%M:%S')
        fileHandler = logging.FileHandler(PBConfig.get('log_file_path'))
        fileHandler.setFormatter(logFormatter)
        logging.getLogger().addHandler(fileHandler)
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        logging.getLogger().addHandler(consoleHandler)
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        print(str(args.config) + " config file is not valid or not found. Please check integrity of the file")
        error_state()

    # Process arguments
    if args.sync == "all" or args.sync == "force":
        # Do not progress further if we're in an error state
        if PBParser.check_error_state():
            logging.error("Repository is currently in an error state. Please fix issues in your workspace before running PBSync")
            logging.info("If you have already fixed the problem, you may remove " + PBConfig.get('error_file') + " from your project folder & run StartProject bat file again.")
            error_state(True)

        # Firstly, check our remote connection before doing anything
        remote_state, remote_url = PBTools.check_remote_connection()
        if not remote_state:
            logging.error("Remote connection was not successful. Please verify you have a valid git remote URL & internet connection. Current git remote URL: " + remote_url)
            error_state()
        else:
            logging.info("Remote connection is up")

        logging.info("------------------")

        logging.info("Executing " + str(args.sync) + " sync command for PBSync v" + PBConfig.get('pbsync_version'))

        logging.info("------------------")

        git_version_result = PBParser.compare_git_version(PBConfig.get('supported_git_version'))
        if git_version_result == -2:
            # Handle parse error first, in case of possibility of getting expection in following get_git_version() calls
            logging.error("Git is not installed correctly on your system.")
            logging.error("Please install latest Git from https://git-scm.com/download/win")
            error_state()
        elif git_version_result == 0:
            logging.info("Current Git version: " + str(PBParser.get_git_version()))
        elif git_version_result == -1:
            logging.error("Git is not updated to the latest version in your system")
            logging.error("Supported Git Version: " + PBConfig.get('supported_git_version'))
            logging.error("Current Git Version: " + str(PBParser.get_git_version()))
            logging.error("Please install latest Git from https://git-scm.com/download/win")
            error_state()
        elif git_version_result == 1:
            logging.warning("Current Git version is newer than supported one: " + PBParser.get_git_version())
            logging.warning("Supported Git version: " + PBConfig.get('supported_git_version'))
        else:
            logging.error("Git is not installed correctly on your system.")
            logging.error("Please install latest Git from https://git-scm.com/download/win")
            error_state()
        lfs_version_result = PBParser.compare_lfs_version(PBConfig.get('supported_lfs_version'))
        if lfs_version_result == -2:
            # Handle parse error first, in case of possibility of getting expection in following get_git_version() calls
            logging.error("Git LFS is not installed correctly on your system.")
            logging.error("Please install latest Git LFS from https://git-lfs.github.com")
            error_state()
        elif lfs_version_result == 0:
            logging.info("Current Git LFS version: " + str(PBParser.get_lfs_version()))
        elif lfs_version_result == -1:
            logging.error("Git LFS is not updated to the latest version in your system")
            logging.error("Supported Git LFS Version: " + PBConfig.get('supported_lfs_version'))
            logging.error("Current Git LFS Version: " + str(PBParser.get_lfs_version()))
            logging.error("Please install latest Git LFS from https://git-lfs.github.com")
            error_state()
        elif lfs_version_result == 1:
            logging.warning("Current Git LFS version is newer than supported one: " + PBParser.get_lfs_version())
            logging.warning("Supported Git LFS version: " + PBConfig.get('supported_lfs_version'))
        else:
            logging.error("Git LFS is not installed correctly on your system")
            logging.error("Please install latest Git LFS from https://git-lfs.github.com")
            error_state()

        logging.info("------------------")

        # Do not execute if Unreal Editor is running
        if PBTools.check_running_process("UE4Editor.exe"):
            logging.error("Unreal Editor is currently running. Please close it before running PBSync")
            error_state()

        logging.info("Fetching recent changes on the repository...")
        subprocess.call(["git", "fetch", "origin"])

        # Do some housekeeping for git configuration
        setup_git_config()

        # Check if we have correct credentials
        check_git_credentials()

        logging.info("------------------")

        # Execute synchronization part of script if we're on the expected branch, force sync is enabled
        if args.sync == "force" or is_expected_branch():
            resolve_conflicts_and_pull()
            logging.info("------------------")
            
            if PBTools.pbget_pull() != 0:
                logging.error("An error occured while running PBGet. It's likely binary files for this release are not pushed yet. Please request help on #tech-support")
                error_state()
        else:
            logging.warning("Current branch is not set as " + PBConfig.get('expected_branch_name') + ". Auto synchronization will be disabled")

        logging.info("------------------")

        project_version = PBParser.get_project_version()

        if project_version != None:
            logging.info("Current project version: " + project_version)
        else:
            logging.error("Something went wrong while fetching project version. Please request help on #tech-support")
            error_state()
        
        logging.info("------------------")

        logging.info("Checking for engine updates...")
        if sync_file("ProjectBorealis.uproject") != 0:
            logging.error("Something went wrong while updating .uproject file. Please request help on #tech-support")
            error_state()

        engine_version =  PBParser.get_engine_version()

        logging.info("Trying to register current engine build if it exists. Otherwise, required build will be downloaded...")
        if PBTools.run_ue4versionator() != 0:
            logging.error("Something went wrong while registering engine build " + engine_version + ". Please request help on #tech-support")
            error_state()
        else:
            logging.info("Engine build " + engine_version + " successfully registered")
            
        # Clean old engine installations, do that only in expected branch
        if is_expected_branch():
            if PBTools.clean_old_engine_installations():
                logging.info("Old engine installations are successfully cleaned")
            else:
                logging.warning("Something went wrong while cleaning old engine installations. You may want to clean them manually.")

        logging.info("------------------")

        if PBTools.check_ue4_file_association():
            os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")
        else:
            logging.error(".uproject extension is not correctly set into Unreal Engine. Make sure you have Epic Games Launcher installed. If problem still persists, please get help from #tech-support.")
            error_state()

    elif args.sync == "engine":
        if args.repository is None:
            logging.error("--repository <URL> argument should be provided with --sync engine command")
            sys.exit(1)
        engine_version = PBParser.get_latest_available_engine_version(str(args.repository))
        if engine_version is None:
            logging.error("Error while trying to fetch latest engine version")
            sys.exit(1)
        if not PBParser.set_engine_version(engine_version):
            logging.error("Error while trying to update engine version in .uproject file")
            sys.exit(1)
        logging.info("Successfully changed engine version as " + str(engine_version))

    elif args.sync == "ddc" or args.sync == "DDC":
        generate_ddc_command()

    elif args.print == "latest-engine":
        if args.repository is None:
            logging.error("--repository <URL> argument should be provided with --print latest-engine command")
            sys.exit(1)
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
            logging.info("Successfully increased project version")
        else:
            logging.error("Error occured while trying to increase project version")
            sys.exit(1)

    elif not (args.wipe is None):
        if wipe_workspace():
            logging.info("Workspace wipe successful")
            input("Press enter to quit...")
        else:
            logging.error("Something went wrong while wiping the workspace")
            sys.exit(1)
    
    elif args.clean == "engine":
        if not PBTools.clean_old_engine_installations():
            logging.error("Something went wrong on engine installation root folder clean process")
            sys.exit(1)

    elif not (args.publish is None):
        if not PBTools.push_build(args.publish):
            logging.error("Something went wrong while pushing a new playable build.")
            sys.exit(1)

    elif not (args.push is None):
        pass
    
    else:
        logging.error("Please start PBSync from StartProject.bat, or pass proper argument set to the executable")
        error_state()

    if not (args.push is None):
        project_version = PBParser.get_project_version()
        logging.info("Initiating PBGet to push " + project_version + " binaries...")
        result = PBTools.pbget_push(str(args.push))
        if int(result) == 1:
            logging.error("Error occured while pushing binaries for " + project_version)
            sys.exit(1)

if __name__ == '__main__':
    if "Scripts" in os.getcwd():
        # Working directory fix for scripts calling PBSync from Scripts folder
        os.chdir("..")
    main()
