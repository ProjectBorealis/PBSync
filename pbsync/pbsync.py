import subprocess
import os.path
import os
import sys
import argparse

from pbpy import pblog
from pbpy import pbhub
from pbpy import pbtools
from pbpy import pbunreal
from pbpy import pbgit
from pbpy import pbconfig
from pbpy import pbversion
from pbpy import pbdispatch

default_config_name = "PBSync.xml"

def config_handler(config_var, config_parser_func):
    if not pbconfig.generate_config(config_var, config_parser_func):
        # Logger is not initialized yet, so use print instead
        print(str(config_var) + " config file is not valid or not found. Please check integrity of the file")
        sys.exit(1)

def sync_handler(sync_val, repository_val = None, bundle_name = None):
    if sync_val == "all" or sync_val == "force":
        # Firstly, check our remote connection before doing anything
        remote_state, remote_url = pbgit.check_remote_connection()
        if not remote_state:
            pbtools.error_state("Remote connection was not successful. Please verify you have a valid git remote URL & internet connection. Current git remote URL: " + remote_url)
        else:
            pblog.info("Remote connection is up")

        pblog.info("------------------")

        pblog.info("Executing " + str(sync_val) + " sync command")
        pblog.info("PBpy Module Version: " + pbversion.pbpy_ver)
        pblog.info("PBSync Executable Version: " + pbversion.pbsync_ver)

        pblog.info("------------------")

        detected_git_version = pbgit.get_git_version()
        if detected_git_version == pbconfig.get('supported_git_version'):
            pblog.info("Current Git version: " + detected_git_version)
        else:
            pblog.error("Git is not updated to the supported version in your system")
            pblog.error("Supported Git Version: " + pbconfig.get('supported_git_version'))
            pblog.error("Current Git Version: " + detected_git_version)
            pblog.error("Please install supported git version from https://github.com/microsoft/git/releases")
            pblog.error("Visit https://github.com/ProjectBorealisTeam/pb/wiki/Prerequisites for installation instructions")
            pbtools.error_state()
        
        detected_lfs_version = pbgit.get_lfs_version()
        if detected_lfs_version == pbconfig.get('supported_lfs_version'):
            pblog.info("Current Git LFS version: " + detected_lfs_version)
        else:
            pblog.error("Git LFS is not updated to the supported version in your system")
            pblog.error("Supported Git LFS Version: " + pbconfig.get('supported_lfs_version'))
            pblog.error("Current Git LFS Version: " + detected_lfs_version)
            pblog.error("Please install latest Git LFS from https://git-lfs.github.com")
            pbtools.error_state()

        pblog.info("------------------")
        
        # Do not execute if Unreal Editor is running
        if pbtools.check_running_process("UE4Editor.exe"):
            pbtools.error_state("Unreal Editor is currently running. Please close it before running PBSync. If editor is not running, but you're somehow getting that error, please restart your system")

        pblog.info("Fetching recent changes on the repository...")
        subprocess.call(["git", "fetch", "origin"])

        # Do some housekeeping for git configuration
        pbgit.setup_config()

        # Check if we have correct credentials
        pbgit.check_credentials()

        pblog.info("------------------")

        # Execute synchronization part of script if we're on the expected branch, or force sync is enabled
        is_on_expected_branch = pbgit.compare_with_current_branch_name(pbconfig.get('expected_branch_name'))
        if sync_val == "force" or is_on_expected_branch:
            pbtools.resolve_conflicts_and_pull() 

            pblog.info("------------------")

            project_version = pbunreal.get_project_version()
            if project_version != None:
                pblog.info("Current project version: " + project_version)
            else:
                pbtools.error_state("Something went wrong while fetching project version. Please request help on #tech-support")
            
            if pbhub.is_pull_binaries_required():
                pblog.info("Binaries are not up-to-date, trying to pull new binaries...")
                if pbhub.pull_binaries(project_version):
                    pblog.info("Binaries are pulled successfully")
                else:
                    pbtools.error_state("An error occured while pulling binaries", True)
            else:
                pblog.info("Binaries are up-to-date")   
        else:
            pblog.warning("Current branch is not supported for repository synchronizarion: " + pbconfig.get('expected_branch_name') + ". Auto synchronization will be disabled")

        pblog.info("------------------")

        pblog.info("Checking for engine updates...")
        if pbgit.sync_file("ProjectBorealis.uproject") != 0:
            pbtools.error_state("Something went wrong while updating .uproject file. Please request help on #tech-support")

        engine_version =  pbunreal.get_engine_version()

        pblog.info("Trying to register current engine build if it exists. Otherwise, required build will be downloaded...")
        
        symbols_needed = pbunreal.is_versionator_symbols_enabled()

        bundle_name = None
        if is_on_expected_branch:
            # Expected branch should use deveditor bundle
            bundle_name = pbconfig.get("creative_bundle_name")
        else:
            # Other users should use editor bundle, which also has debug build support
            bundle_name = pbconfig.get("default_bundle_name")

        if pbunreal.run_ue4versionator(bundle_name, symbols_needed) != 0:
            pblog.error("Something went wrong while registering engine build " + bundle_name + "-" + engine_version + ". Please request help on #tech-support")
            sys.exit(1)
        else:
            pblog.info("Engine build " + bundle_name + "-" + engine_version + " successfully registered")
            
        # Clean old engine installations, do that only in expected branch
        if is_on_expected_branch:
            if pbunreal.clean_old_engine_installations():
                pblog.info("Old engine installations are successfully cleaned")
            else:
                pblog.warning("Something went wrong while cleaning old engine installations. You may want to clean them manually.")

        pblog.info("------------------")

        if pbunreal.check_ue4_file_association():
            os.startfile(os.getcwd() + "\\ProjectBorealis.uproject")
        else:
            pbtools.error_state(".uproject extension is not correctly set into Unreal Engine. Make sure you have Epic Games Launcher installed. If problem still persists, please get help from #tech-support.")

    elif sync_val == "engineversion":
        if repository_val is None:
            pblog.error("--repository <URL> argument should be provided with --sync engine command")
            sys.exit(1)
        engine_version = pbunreal.get_latest_available_engine_version(str(repository_val))
        if engine_version is None:
            pblog.error("Error while trying to fetch latest engine version")
            sys.exit(1)
        if not pbunreal.set_engine_version(engine_version):
            pblog.error("Error while trying to update engine version in .uproject file")
            sys.exit(1)
        pblog.info("Successfully changed engine version as " + str(engine_version))

    elif sync_val == "ddc" or sync_val == "DDC":
        pbunreal.generate_ddc_data()
    
    elif sync_val == "binaries":
        project_version = pbunreal.get_project_version()
        if pbhub.pull_binaries(project_version, True):
            pblog.info("Binaries for " + project_version + " pulled & extracted successfully")
        else:
            pblog.error("Failed to pull binaries for " + project_version)
            sys.exit(1)

    elif sync_val == "engine":
        # Pull engine build with ue4versionator & register it
        if bundle_name is None:
            # If --bundle parameter is not provided, use defaults from current git branch
            is_on_expected_branch = pbgit.compare_with_current_branch_name(pbconfig.get('expected_branch_name'))
            if is_on_expected_branch:
                # Expected branch should use deveditor bundle
                bundle_name = pbconfig.get("creative_bundle_name")
            else:
                # Other users should use editor bundle, which also has debug build support
                bundle_name = pbconfig.get("default_bundle_name")
        
        engine_version = pbunreal.get_engine_version()

        if pbunreal.run_ue4versionator(bundle_name, False) != 0:
            pblog.error("Something went wrong while registering engine build " + bundle_name + "-" + engine_version)
            sys.exit(1)
        else:
            pblog.info("Engine build " + bundle_name + "-" + engine_version + " successfully registered")

def clean_handler(clean_val):
    if clean_val == "workspace":
        if pbtools.wipe_workspace():
            pblog.info("Workspace wipe successful")
            input("Press enter to quit...")
        else:
            pblog.error("Something went wrong while wiping the workspace")
            sys.exit(1)

    elif clean_val == "engine":
        if not pbtools.clean_old_engine_installations():
            pblog.error("Something went wrong on engine installation root folder clean process")
            sys.exit(1)

def print_handler(print_val, repository_val = None):
    if print_val == "latest-engine":
        if repository_val is None:
            pblog.error("--repository <URL> argument should be provided with --print latest-engine command")
            sys.exit(1)
        engine_version = pbunreal.get_latest_available_engine_version(str(repository_val))
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end="")
    
    elif print_val == "current-engine":
        engine_version = pbunreal.get_engine_version()
        if engine_version is None:
            sys.exit(1)
        print(engine_version, end="")
    
    elif print_val == "project":
        project_version = pbunreal.get_project_version()
        if project_version is None:
            sys.exit(1)
        print(project_version, end="")

def autoversion_handler(autoversion_val):
    if pbunreal.project_version_increase(autoversion_val):
        pblog.info("Successfully increased project version")
    else:
        pblog.error("Error occured while trying to increase project version")
        sys.exit(1)

def publish_handler(publish_val, dispatch_exec_path):
    if dispatch_exec_path is None:
        pblog.error("--dispatch argument should be provided for --publish command")
        sys.exit(1)

    if not pbdispatch.push_build(publish_val, dispatch_exec_path, pbconfig.get('dispatch_config'), pbconfig.get('dispatch_stagedir'), pbconfig.get('dispatch_drm')):
        pblog.error("Something went wrong while pushing a new playable build.")
        sys.exit(1)

def push_handler(file_name):
    project_version = pbunreal.get_project_version()
    pblog.info("Attaching " + file_name + " into GitHub release " + project_version)
    if not pbhub.push_package(project_version, file_name):
        pblog.error("Error occured while pushing package for release " + project_version)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Project Borealis Workspace Synchronization Tool | PBpy Module Version: " + pbversion.pbpy_ver + " | PBSync Executable Version: " + pbversion.pbsync_ver)

    parser.add_argument("--sync", help="Main command for the PBSync, synchronizes the project with latest changes in repo, and does some housekeeping",
    choices=["all", "binaries", "engineversion", "engine", "force", "ddc"])
    parser.add_argument("--printversion", help="Prints requested version information into console. latest-engine command needs --repository parameter",
    choices=["current-engine", "latest-engine", "project"])
    parser.add_argument("--repository", help="Required gcloud repository url for --printversion latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="Automatic version update for project version", choices=["hotfix", "stable", "public"])
    parser.add_argument("--clean", help="""Do cleanup according to specified argument. If engine is provided, old engine installations will be cleared
    If workspace is provided, workspace will be reset with latest changes from current branch (Not revertable)""", choices=["engine", "workspace"])
    parser.add_argument("--config", help="Path of config XML file. If not provided, ./" + default_config_name + " is used as default", default=default_config_name)
    parser.add_argument("--push", help="Push provided file into release of current project version")
    parser.add_argument("--publish", help="Publishes a playable build with provided build type", choices=["internal", "playtester"])
    parser.add_argument("--dispatch", help="Required dispastch executable path for --publish command")
    parser.add_argument("--bundle", help="Required archive bundle name for --sync engine command. If not provided, ue4versionator will download without a bundle name")
    parser.add_argument("--debugpath", help="If provided, PBSync will run in provided path")
    parser.add_argument("--debugbranch", help="If provided, PBSync will use provided branch as expected branch")
    
    if len(sys.argv) > 0:
        args = parser.parse_args()
    else:
        print("At least one valid argument should be passed!")
        sys.exit(1)

    if not (args.debugpath is None):
        # Work on provided debug path
        os.chdir(str(args.debugpath))

    # Parser function object for PBSync config file
    def pbsync_config_parser_func (root): return {
        'supported_git_version': root.find('git/version').text,
        'supported_lfs_version': root.find('git/lfsversion').text,
        'expected_branch_name': root.find('git/expectedbranch').text if args.debugbranch is None else str(args.debugbranch),
        'lfs_lock_url': root.find('git/lfslockurl').text,
        'git_url': root.find('git/url').text,
        'checksum_file': root.find('git/checksumfile').text,
        'log_file_path': root.find('log/file').text,
        'versionator_config_path': root.find('versionator/configpath').text,
        'default_bundle_name': root.find('versionator/defaultbundle').text,
        'creative_bundle_name': root.find('versionator/creativebundle').text,
        'engine_base_version': root.find('project/enginebaseversion').text,
        'uproject_name': root.find('project/uprojectname').text,
        'defaultgame_path': root.find('project/defaultgameinipath').text,
        'dispatch_config': root.find('dispatch/config').text,
        'dispatch_drm': root.find('dispatch/drm').text,
        'dispatch_stagedir': root.find('dispatch/stagedir').text
    }

    # Preparation
    config_handler(args.config, pbsync_config_parser_func)
    pblog.setup_logger(pbconfig.get('log_file_path'))

    # Do not process further if we're in an error state
    if pbtools.check_error_state():
        pbtools.error_state("""Repository is currently in an error state. Please fix issues in your workspace before running PBSync
        If you have already fixed the problem, you may remove """ + pbtools.error_file + " from your project folder & run StartProject bat file again.", True)

    # Parse args
    if not (args.sync is None):
        sync_handler(args.sync, args.repository, args.bundle)
    elif not (args.print is None):
        print_handler(args.print, args.repository)
    elif not (args.autoversion is None):
        autoversion_handler(args.autoversion)
    elif not (args.clean is None):
        clean_handler(args.clean)
    elif not (args.publish is None):
        publish_handler(args.publish, args.dispatch)
    elif not (args.push is None):
        push_handler(args.push)
    else:
        pblog.error("At least one valid argument should be passed!")

if __name__ == '__main__':
    if "Scripts" in os.getcwd():
        # Working directory fix for scripts calling PBSync from Scripts folder
        os.chdir("..")
    main()
