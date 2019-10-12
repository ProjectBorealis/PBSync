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
    return subprocess.call(["git", "checkout", "-f", sync_head, "--", file_path])

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
    sync_file(PBConfig.get('git_hooks_path'))
    subprocess.call(["git", "config", "core.hooksPath", PBConfig.get('git_hooks_path')])
    subprocess.call(["git", "config", "core.autocrlf", "true"])
    subprocess.call(["git", "config", "help.autocorrect", "true"])
    subprocess.call(["git", "config", "commit.template", "git-hooks/gitmessage.txt"])
    subprocess.call(["git", "config", "merge.conflictstyle", "diff3"])
    subprocess.call(["git", "config", "push.default", "current"])
    # subprocess.call(["git", "show-ref", "-s", "|", "git", "commit-graph write", "--stdin-commits"]) # Broken in git 2.23

def generate_ddc_command():
    logging.info("Generating DDC data, please wait... (This may take up to one hour only for the initial run)")
    state, err = PBTools.generate_ddc_data()
    logging.info("DDC generate command has exited with " + str(err))
    if state == 0:
        logging.info("DDC data successfully generated & versioned!")
    elif state == 1:
        logging.error("Error occured while trying to read project version for DDC data generation. Please get support from #tech-support")
        sys.exit(1)
    elif state == 2:
        logging.error("Generated DDC data was smaller than expected. Please get support from #tech-support")
        sys.exit(1)
    elif state == 3:
        logging.error("DDC data was succesffuly generated, but an error occured while versioning your DDC folder. Please get support from #tech-support")
        sys.exit(1)

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
     # "git branch --show-current" is a new feature in git 2.22
    output = get_current_branch_name()
    
    if output != PBConfig.get('expected_branch_name'):
        return False

    # In any case, always set upstream to track same branch (only if we're on expected branch)
    out = subprocess.getoutput(["git", "branch", "--set-upstream-to=origin/" + str(output), str(output)])
    return True

def resolve_conflicts_and_pull():
    # Abort if any merge, rebase or am request is going on at the moment
    abort_merge()

    # Turn off rebase pull & autostash for now
    rebase_switch(False)
    
    # Disable watchman for now
    disable_watchman()

    output = subprocess.getoutput(["git", "status"])

    logging.info("Please wait while getting latest changes on the repository. It may take a while...")

    if "Your branch is ahead of" in str(output):
        abort_merge()
        logging.error("You have non-pushed commits. Please push them first to process further. If you're not sure about how to do that, request help from #tech-support")
        sys.exit(1)

    elif "nothing to commit, working tree clean" in str(output):
        logging.info("Resetting your local workspace to latest FETCH_HEAD...")
        subprocess.call(["git", "fetch", "origin", get_current_branch_name()])
        subprocess.call(["git", "reset", "--hard", "FETCH_HEAD"])
        logging.info("Pulled changes without any conflict")

    else:
        output = subprocess.getoutput(["git", "pull"])
        logging.info(str(output))

        backup_folder = 'Backup/' + datetime.datetime.now().strftime("%I%M%Y%m%d")
        
        if "There is no tracking information for the current branch" in str(output):
            abort_merge()
            logging.error("Aborting the merge. Your local branch is not tracked by remote anymore. Please request help on #tech-support to solve the problem")
            sys.exit(1)

        elif "Please commit your changes or stash them before you merge" in str(output):
            logging.warning("Conflicts found with uncommitted files in your workspace. Another developer made changes on the files listed below, and pushed them into the repository before you:")
            file_list = []
            for file_path in output.splitlines():
                if file_path[0] == '\t':
                    stripped_filename = file_path.strip()
                    file_list.append(stripped_filename)
                    logging.info(stripped_filename)
            
            response = input("Files listed above will be overwritten by incoming versions from repository and your work will be backed up in Backup folder. Do you want to continue? [y/N]")
            if(response != "y" and response != "Y"):
                logging.error("Please request help on #tech-support to resolve your conflicts")
                sys.exit(1)

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
                    logging.warning("Something went wrong while reverting the file. Trying to remove it from the workspace...")
                    if remove_file(file_path) == False:
                        logging.error("Something went wrong while trying to resolve conflicts on " + file_path + ". Please request help on #tech-support")
                        sys.exit(1)

                logging.info("Conflict resolved for " + file_path)
                logging.info("File backed up in " + file_backup_path)
            
            logging.info("All conflicts are resolved. Trying to pull changes one more time...")
            status = subprocess.call(["git", "pull"])

            if status == 0:
                logging.info("Synchronization successful!")
            else:
                logging.error("Something went wrong while trying to pull new changes on repository. Please request help on #tech-support")
                sys.exit(1)
        
        elif "The following untracked working tree files would be overwritten by merge" in str(output):
            file_list = []
            for file_path in output.splitlines():
                if file_path[0] == '\t':
                    stripped_filename = file_path.strip()
                    file_list.append(stripped_filename)
                    logging.info(stripped_filename)
            
            response = input("Untracked files listed above will be overwritten with new versions, do you confirm? (This can't be reverted) [y/N] ")

            if response == "y" or response == "Y":
                for file_path in file_list:
                    remove_file(file_path)
                    logging.warning("Removed untracked file: " + str(file_path))
                logging.info("Running synchronization command again...")
                # Run the whole function again, we have resolved the overwritten untracked file problem
                resolve_conflicts_and_pull()
                return
            else:
                logging.error("Aborting...")
                abort_merge()
                logging.error("Something went wrong while trying to pull new changes on repository. Please request help on #tech-support")
                sys.exit(1)
        elif "Your local changes to the following files would be overwritten by merge" in str(output):
            # That was mostly caused by checked out ProjectBorealis.uproject file, it's probably fixed after latest changes on that part
            logging.error("Upcoming files will overwrite your local changes. Please request help on #tech-support to solve possible conflicts on your repository.")
            sys.exit(1)
        elif "Aborting" in str(output):
            logging.error("Something went wrong while trying to pull new changes on repository. Please request help on #tech-support")
            sys.exit(1)
        else:
            logging.info("Pulled latest changes without any conflict")

    # Revert rebase config back
    rebase_switch(True)
############################################################################

def main():
    parser = argparse.ArgumentParser(description="Project Borealis Workspace Synchronization Tool")

    parser.add_argument("--sync", help="[force, all, engine, ddc] Main command for the PBSync, synchronizes the project with latest changes in repo, and does some housekeeping")
    parser.add_argument("--print", help="[current-engine, latest-engine, project] Prints requested version information into console. latest-engine command needs --repository parameter")
    parser.add_argument("--repository", help="<URL> Required repository url for --print latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="[minor, major, release] Automatic version update for project version")
    parser.add_argument("--wipe", help="[latest] Wipe the workspace and get latest changes from current branch (Not revertable)")
    parser.add_argument("--clean", help="[engine] Do cleanup according to specified argument")
    parser.add_argument("--config", help="Path of config XML file. If not provided, ./PBSync.xml is used as default")
    args = parser.parse_args()

    # Workaround for old repositories. they need the xml file
    out = subprocess.getoutput(["git", "fetch", "origin"])
    sync_file("PBSync.xml")
    ##########################################################

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
        print("A valid config file should be provided with --config argument")
        sys.exit(1)

    # Workaround for old repositories. Revert that checked out specific file back
    remove_file("PBSync.xml")
    out = subprocess.getoutput(["git", "reset", "--", "PBSync.xml"])
    out = subprocess.getoutput(["git", "add", "PBSync.xml"])
    out = subprocess.getoutput(["git", "reset", "--", "PBSync.xml"])
    # Try checkout, in case of file already exists in current state of the branch
    out = subprocess.getoutput(["git", "checkout", "PBSync.xml"])
    ##########################################################

    # Process arguments
    if args.sync == "all" or args.sync == "force":
        logging.info("Executing " + str(args.sync) + " sync command for PBSync v" + PBConfig.get('pbsync_version'))
        
        logging.info("------------------")

        git_version_result = PBParser.compare_git_version(PBConfig.get('supported_git_version'))
        if git_version_result == -2:
            # Handle parse error first, in case of possibility of getting expection in following get_git_version() calls
            logging.error("Git is not installed correctly on your system.")
            logging.error("Please install latest Git from https://git-scm.com/download/win")
            sys.exit(1)
        elif git_version_result == 0:
            logging.info("Current Git version: " + PBParser.get_git_version())
        elif git_version_result == -1:
            logging.error("Git is not updated to the latest version in your system")
            logging.error("Supported Git Version: " + PBConfig.get('supported_git_version'))
            logging.error("Current Git Version: " + PBParser.get_git_version())
            logging.error("Please install latest Git from https://git-scm.com/download/win")
            sys.exit(1)
        elif git_version_result == 1:
            logging.warning("Current Git version is newer than supported one: " + PBParser.get_git_version())
            logging.warning("Supported Git version: " + PBConfig.get('supported_git_version'))
        else:
            logging.error("Git is not installed correctly on your system.")
            logging.error("Please install latest Git from https://git-scm.com/download/win")
            sys.exit(1)
        lfs_version_result = PBParser.compare_lfs_version(PBConfig.get('supported_lfs_version'))
        if lfs_version_result == -2:
            # Handle parse error first, in case of possibility of getting expection in following get_git_version() calls
            logging.error("Git LFS is not installed correctly on your system.")
            logging.error("Please install latest Git LFS from https://git-lfs.github.com")
            sys.exit(1)
        elif lfs_version_result == 0:
            logging.info("Current Git LFS version: " + PBParser.get_lfs_version())
        elif lfs_version_result == -1:
            logging.error("Git LFS is not updated to the latest version in your system")
            logging.error("Supported Git LFS Version: " + PBConfig.get('supported_lfs_version'))
            logging.error("Current Git LFS Version: " + PBParser.get_lfs_version())
            logging.error("Please install latest Git LFS from https://git-lfs.github.com")
            sys.exit(1)
        elif lfs_version_result == 1:
            logging.warning("Current Git LFS version is newer than supported one: " + PBParser.get_lfs_version())
            logging.warning("Supported Git LFS version: " + PBConfig.get('supported_lfs_version'))
        else:
            logging.error("Git LFS is not installed correctly on your system")
            logging.error("Please install latest Git LFS from https://git-lfs.github.com")
            sys.exit(1)

        logging.info("------------------")

        # Do not execute if Unreal Editor is running
        if PBTools.check_running_process("UE4Editor.exe"):
            logging.error("Unreal Editor is currently running. Please close it before running PBSync")
            sys.exit(1)

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
            clean_cache()
            
            if PBTools.run_pbget() != 0:
                logging.error("An error occured while running PBGet. It's likely binary files for this release are not pushed yet. Please request help on #tech-support")
                sys.exit(1)
        else:
            logging.warning("Current branch is not set as " + PBConfig.get('expected_branch_name') + ". Auto synchronization will be disabled")

        logging.info("------------------")

        project_version = PBParser.get_project_version()

        if project_version != None:
            logging.info("Current project version: " + project_version)
        else:
            logging.error("Something went wrong while fetching project version. Please request help on #tech-support")
            sys.exit(1)
        
        logging.info("------------------")

        logging.info("Checking for engine updates...")
        if sync_file("ProjectBorealis.uproject") != 0:
            logging.error("Something went wrong while updating .uproject file. Please request help on #tech-support")
            sys.exit(1)

        engine_version =  PBParser.get_engine_version()

        logging.info("Trying to register current engine build if it exists. Otherwise, required build will be downloaded...")
        if PBTools.run_ue4versionator() != 0:
            logging.error("Something went wrong while registering engine build " + engine_version + ". Please request help on #tech-support")
            sys.exit(1)
        else:
            logging.info("Engine build " + engine_version + " successfully registered")
            
        # Clean old engine installations, do that only in expected branch
        if is_expected_branch():
            if PBTools.clean_old_engine_installations():
                logging.info("Old engine installations are successfully cleaned")
            else:
                logging.warning("Something went wrong while cleaning old engine installations. You may clean them manually.")

        logging.info("------------------")
        
        # Generate DDC data
        if PBParser.ddc_needs_regeneration():
            logging.info("DDC generation is required for this project workspace. Initial DDC data generation is highly recommended to prevent possible crashes, shader calculations & slowdowns in editor.")
            response = input("Do you want to generate DDC data (It may take up to one hour)? If you wish, you can do that another time. [y/N]: ")
            if "y" in response or "Y" in response:
                generate_ddc_command()
            else:
                logging.warning("DDC data won't be generated this time. On your next editor launch, you will be asked again for that.")

        # Wait a little bit after DDC tool
        time.sleep(5)

        # Run watchman in any case it's disabled
        enable_watchman()

        os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")

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
    else:
        logging.error("Please start PBSync from StartProject.bat, or pass proper argument set to the executable")
        sys.exit(1)
        

if __name__ == '__main__':
    if "Scripts" in os.getcwd():
        # Exception for scripts running PBSync from Scripts folder
        os.chdir("..")
    main()
