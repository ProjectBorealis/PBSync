from pbpy.pbtools import error_state
import os.path
import os
import sys
import argparse
import webbrowser
import threading
import multiprocessing

from pathlib import Path

from pbpy import pblog
from pbpy import pbgh
from pbpy import pbtools
from pbpy import pbunreal
from pbpy import pbgit
from pbpy import pbconfig
from pbpy import pbpy_version
from pbpy import pbdispatch
from pbpy import pbuac

import pbgui.main
import pbgui.gateway

try:
    import pbsync_version
except ImportError:
    from pbsync import pbsync_version

default_config_name = "PBSync.xml"


def config_handler(config_var, config_parser_func):
    if not pbconfig.generate_config(config_var, config_parser_func):
        # Logger is not initialized yet, so use print instead
        error_state(f"{str(config_var)} config file is not valid or not found. Please check the integrity of the file", hush=True, term=True)


def sync_handler(sync_val: str, repository_val=None, requested_bundle_name=None):
    sync_val = sync_val.lower()

    if sync_val == "all" or sync_val == "force" or sync_val == "partial":
        # Firstly, check our remote connection before doing anything
        remote_state, remote_url = pbgit.check_remote_connection()
        if not remote_state:
            error_state(
                f"Remote connection was not successful. Please verify that you have a valid git remote URL and internet connection. Current git remote URL: {remote_url}")
        else:
            pblog.info("Remote connection is up")

        pblog.info("------------------")

        pblog.info(f"Executing {sync_val} sync command")
        pblog.info(f"PBpy Library Version: {pbpy_version.ver}")
        pblog.info(f"PBSync Program Version: {pbsync_version.ver}")

        pblog.info("------------------")

        detected_git_version = pbgit.get_git_version()
        needs_git_update = False
        if detected_git_version == pbconfig.get('supported_git_version'):
            pblog.info(f"Current Git version: {detected_git_version}")
        else:
            needs_git_update = True
            if ("vfs" not in pbconfig.get('supported_git_version') or "vfs" in detected_git_version) and sys.platform == "win32" or sys.platform == "darwin":
                pblog.info("Attempting auto-update of Git...")
                if sys.platform == "win32":
                    proc = pbtools.run([pbgit.get_git_executable(), "update-git-for-windows", "-y"])
                else:
                    proc = pbtools.run([pbgit.get_git_executable(), "update-microsoft-git"])
                # if non-zero, error out
                if proc.returncode:
                    pblog.warning("Git auto-update failed. Please try manually:")
                else:
                    needs_git_update = False
                    input("Launching Git update, please press enter when done installing. ")
            if needs_git_update:
                pblog.error("Git is not updated to the supported version in your system")
                pblog.error(f"Supported Git Version: {pbconfig.get('supported_git_version')}")
                pblog.error(f"Current Git Version: {detected_git_version}")
                pblog.error("Please install the supported Git version from https://github.com/microsoft/git/releases")
                pblog.error(f"Visit {pbconfig.get('git_instructions')} for installation instructions")
                if os.name == "nt":
                    webbrowser.open(f"https://github.com/microsoft/git/releases/download/v{pbconfig.get('supported_git_version')}/Git-{pbconfig.get('supported_git_version')}-64-bit.exe")


        if os.name == "nt" and pbgit.get_git_executable() == "git" and pbgit.get_lfs_executable() == "git-lfs":
            # find Git/cmd/git.exe
            git_paths = [path for path in pbtools.whereis("git") if "cmd" in path.parts]

            if len(git_paths) > 0:
                bundled_git_lfs = False

                is_admin = pbuac.isUserAdmin()

                delete_paths = []

                for git_path in git_paths:
                    # find Git from Git/cmd/git.exe
                    git_root = git_path.parents[1]
                    possible_lfs_paths = ["cmd/git-lfs.exe", "mingw64/bin/git-lfs.exe", "mingw64/libexec/git-core/git-lfs.exe"]
                    for possible_lfs_path in possible_lfs_paths:
                        path = git_root / possible_lfs_path
                        if path.exists():
                            try:
                                if is_admin:
                                    path.unlink()
                                else:
                                    delete_paths.append(str(path))
                            except FileNotFoundError:
                                pass
                            except OSError:
                                pblog.error(f"Git LFS is bundled with Git, overriding your installed version. Please remove {path}.")
                                bundled_git_lfs = True

                if not is_admin and len(delete_paths) > 0:
                    pblog.info("Requesting permission to delete bundled Git LFS which is overriding your installed version...")
                    quoted_paths = [f'"{path}"' for path in delete_paths]
                    delete_cmdline = ["cmd.exe", "/c", "DEL", "/q", "/f"] + quoted_paths
                    try:
                        ret = pbuac.runAsAdmin(delete_cmdline)
                    except OSError:
                        pblog.error("User declined permission. Automatic delete failed.")

                for delete_path in delete_paths:
                    path = Path(delete_path)
                    if path.exists():
                        bundled_git_lfs = True
                        pblog.error(f"Git LFS is bundled with Git, overriding your installed version. Please remove {path}.")

                if bundled_git_lfs:
                    error_state()

        detected_lfs_version = pbgit.get_lfs_version()
        supported_lfs_version = pbconfig.get('supported_lfs_version')
        if detected_lfs_version == supported_lfs_version:
            pblog.info(f"Current Git LFS version: {detected_lfs_version}")
        else:
            pblog.error("Git LFS is not updated to the supported version in your system")
            pblog.error(f"Supported Git LFS Version: {supported_lfs_version}")
            pblog.error(f"Current Git LFS Version: {detected_lfs_version}")
            pblog.error("Please install the supported Git LFS version from https://git-lfs.github.com")
            if os.name == "nt":
                webbrowser.open(f"https://github.com/git-lfs/git-lfs/releases/download/v{supported_lfs_version}/git-lfs-windows-v{supported_lfs_version}.exe")
            needs_git_update = True

        detected_gcm_version = pbgit.get_gcm_version()
        supported_gcm_version_raw = pbconfig.get('supported_gcm_version')
        supported_gcm_version = f"{supported_gcm_version_raw}{pbconfig.get('supported_gcm_version_suffix')}"
        if detected_gcm_version == supported_gcm_version:
            pblog.info(f"Current Git Credential Manager Core version: {detected_gcm_version}")
        else:
            pblog.error("Git Credential Manager Core is not updated to the supported version in your system")
            pblog.error(f"Supported Git Credential Manager Core Version: {supported_gcm_version}")
            pblog.error(f"Current Git Credential Manager Core Version: {detected_gcm_version}")
            if detected_gcm_version.startswith("diff"):
                # remove the old credential helper (it may get stuck, and Core won't be able to install)
                pbtools.run_with_combined_output([pbgit.get_git_executable(), "config", "--unset-all", "credential.helper"])
                pbtools.run_with_combined_output([pbgit.get_git_executable(), "config", "--global", "--unset-all", "credential.helper"])
                exe_location = detected_gcm_version.split(".", 1)[1]
                # if they actually have a Windows program installed, inform them.
                if exe_location.endswith(".exe"):
                    pblog.error(f"It seems like you have another Git credential helper installed at: {exe_location}.")
                    pblog.error("Please uninstall this and Git Credential Manager Core if you have it in \"Add or remove programs\" and then install Git Credential Manager Core again.")
                else:
                    pblog.error("Please uninstall Git Credential Manager Core if you have it in \"Add or remove programs\" and then install Git Credential Manager Core again.")
            pblog.error("Please install the supported Git Credential Manager Core version from https://github.com/microsoft/Git-Credential-Manager-Core/releases")
            if os.name == "nt":
                webbrowser.open(f"https://github.com/microsoft/Git-Credential-Manager-Core/releases/download/v{supported_gcm_version}/gcmcore-win-x86-{supported_gcm_version_raw}.{pbconfig.get('gcm_download_suffix')}.exe")
            needs_git_update = True

        if needs_git_update:
            error_state()

        pblog.info("------------------")

        # Do some housekeeping for git configuration
        pbgit.setup_config()

        # Check if we have correct credentials
        pbgit.check_credentials()

        partial_sync = sync_val == "partial"
        is_ci = pbconfig.get("is_ci")

        status_out = pbtools.run_with_combined_output([pbgit.get_git_executable(), "status", "-uno"]).stdout
        # continue a trivial rebase
        if "rebase" in status_out:
            if pbtools.it_has_any(status_out, "nothing to commit", "git rebase --continue", "all conflicts fixed"):
                pbunreal.ensure_ue_closed()
                rebase_out = pbtools.run_with_combined_output([pbgit.get_git_executable(), "rebase", "--continue"]).stdout
                if pbtools.it_has_any(rebase_out, "must edit all merge conflicts"):
                    # this is an improper state, since git told us otherwise before. abort all.
                    pbgit.abort_all()
            else:
                error_state(f"You are in the middle of a rebase. Changes on one of your commits will be overridden by incoming changes. Please request help in {pbconfig.get('support_channel')} to resolve conflicts, and please do not run UpdateProject until the issue is resolved.",
                                    fatal_error=True)

        current_branch = pbgit.get_current_branch_name()
        expected_branch = pbconfig.get('expected_branch_name')
        is_on_expected_branch = current_branch == expected_branch

        # undo single branch clone
        if not is_ci:
            pbtools.run([pbgit.get_git_executable(), "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"])

        # Execute synchronization part of script if we're on the expected branch, or force sync is enabled
        if sync_val == "force" or is_on_expected_branch:
            if partial_sync:
                pbtools.maintain_repo()
            else:
                pbtools.resolve_conflicts_and_pull()

                pblog.info("------------------")

            project_version = pbunreal.get_project_version()
            is_custom_version = pbunreal.is_using_custom_version()
            if project_version is not None:
                if is_custom_version:
                    pblog.info(f"User selected project version: {project_version}")
                else:
                    pblog.info(f"Current project version: {project_version}")
            else:
                error_state(f"Something went wrong while fetching project version. Please request help in {pbconfig.get('support_channel')}.")

            checksum_json_path = pbconfig.get("checksum_file")
            if is_custom_version:
                # checkout old checksum file from tag
                pbgit.sync_file(checksum_json_path, project_version)

            if pbgh.is_pull_binaries_required():
                pblog.info("Binaries are not up to date, pulling new binaries...")
                ret = pbgh.pull_binaries(project_version)
                if ret == 0:
                    pblog.success("Binaries were pulled successfully!")
                elif ret < 0:
                    error_state("Binaries pull failed, please view log for instructions.")
                elif ret > 0:
                    error_state(f"An error occurred while pulling binaries. Please request help in {pbconfig.get('support_channel')} to resolve it, and please do not run UpdateProject until the issue is resolved.", True)
            else:
                pblog.success("Binaries are up to date!")

            # restore checksum file
            if is_custom_version:
                pbgit.sync_file(checksum_json_path, "HEAD")
        elif pbconfig.get_user("project", "autosync", default=False):
            pbtools.resolve_conflicts_and_pull()
        else:
            pblog.info(f"Current branch does not need auto synchronization: {pbgit.get_current_branch_name()}.")
            pbtools.maintain_repo()

        fix_attr_thread = threading.Thread(target=pbgit.fix_lfs_ro_attr)
        fix_attr_thread.start()

        pblog.info("------------------")

        pblog.info("Checking for engine updates...")
        engine_version = pbunreal.get_engine_version_with_prefix()
        if engine_version is not None:
            pblog.info("Registering current engine build if it exists. Otherwise, the build will be downloaded...")

            symbols_needed = pbunreal.is_versionator_symbols_enabled()
            bundle_name = pbconfig.get("uev_ci_bundle") if pbconfig.get("is_ci") else pbconfig.get("uev_default_bundle")
            bundle_name = pbconfig.get_user("project", "bundle", default=bundle_name)

            if pbunreal.download_engine(bundle_name, symbols_needed):
                pblog.info(f"Engine build {bundle_name}-{engine_version} successfully registered")
            else:
                error_state(f"Something went wrong while registering engine build {bundle_name}-{engine_version}. Please request help in {pbconfig.get('support_channel')}.")

            # Clean old engine installations, do that only in expected branch
            if is_on_expected_branch:
                if pbunreal.clean_old_engine_installations():
                    pblog.info("Old engine installations are successfully cleaned")
                else:
                    pblog.warning("Something went wrong while cleaning old engine installations. You may want to clean them manually.")

        pblog.info("------------------")

        pblog.info("Updating Unreal configuration settings")
        pbunreal.update_source_control()

        pblog.info("Finishing LFS read flag fix...")
        fix_attr_thread.join()
        pblog.info("Finished LFS read flag fix.")

        launch_pref = pbconfig.get_user("project", "launch", "editor")
        if launch_pref == "vs":
            os.startfile(pbunreal.get_sln_path())
        elif launch_pref == "rider":
            rider_bin = pbtools.get_one_line_output(["echo", "%Rider for Unreal Engine%"])
            rider_bin = rider_bin.replace(";", "")
            rider_bin = rider_bin.replace("\"", "")
            pbtools.run_non_blocking(f'"{rider_bin}\\rider64.exe" "{str(pbunreal.get_sln_path().resolve())}"')
        elif pbunreal.is_ue_closed():
            if launch_pref == "editor":
                if pbunreal.check_ue_file_association():
                    uproject_file = pbconfig.get('uproject_name')
                    path = str(Path(uproject_file).resolve())
                    try:
                        os.startfile(path)
                    except NotImplementedError:
                        if sys.platform.startswith('linux'):
                            pbtools.run_non_blocking(f"xdg-open {path}")
                        else:
                            pblog.info(f"You may now launch {uproject_file} with Unreal Engine.")
                else:
                    error_state(f".uproject extension is not correctly set into Unreal Engine. Make sure you have Epic Games Launcher installed. If problem still persists, please get help in {pbconfig.get('support_channel')}.")
            # TODO
            #elif launch_pref == "debug":
            #    pbtools.run_non_blocking(f"\"{str(pbunreal.get_devenv_path())}\" \"{str(pbunreal.get_sln_path())}\" /DebugExe \"{str(pbunreal.get_editor_path())}\" \"{str(pbunreal.get_uproject_path())}\" -skipcompile")


    elif sync_val == "engineversion":
        repository_val = pbunreal.get_versionator_gsuri(repository_val)
        if repository_val is None:
                error_state("--repository <URL> argument should be provided with --sync engine command")
        engine_version = pbunreal.get_latest_available_engine_version(str(repository_val))
        if engine_version is None:
            error_state("Error while fetching latest engine version")
        if not pbunreal.set_engine_version(engine_version):
            error_state("Error while updating engine version in .uproject file")
        pblog.info(f"Successfully changed engine version as {str(engine_version)}")

    elif sync_val == "ddc":
        pbunreal.generate_ddc_data()

    elif sync_val == "binaries":
        project_version = pbunreal.get_project_version()
        ret = pbgh.pull_binaries(project_version, True)
        if ret == 0:
            pblog.info(f"Binaries for {project_version} pulled and extracted successfully")
        else:
            error_state(f"Failed to pull binaries for {project_version}")

    elif sync_val == "engine":
        # Pull engine build with ueversionator and register it
        if requested_bundle_name is None:
            requested_bundle_name = pbconfig.get("uev_ci_bundle") if pbconfig.get("is_ci") else pbconfig.get("uev_default_bundle")
            requested_bundle_name = pbconfig.get_user("project", "bundle", default=requested_bundle_name)

        engine_version = pbunreal.get_engine_version_with_prefix()
        symbols_needed = pbunreal.is_versionator_symbols_enabled()
        if pbunreal.download_engine(requested_bundle_name, symbols_needed):
            pblog.info(f"Engine build {requested_bundle_name}-{engine_version} successfully registered")
            if pbconfig.get("is_ci"):
                keep = 3
                pblog.info(f"Keeping the last {keep} engine versions and removing the rest.")
                pbunreal.clean_old_engine_installations(keep=keep)
        else:
            error_state(f"Something went wrong while registering engine build {requested_bundle_name}-{engine_version}")


def build_handler(build_val):
    if build_val == "sln":
        pbunreal.generate_project_files()
    elif build_val == "source":
        pbunreal.build_source()
    elif build_val == "internal":
        pbunreal.build_game("Test")
    elif build_val == "game":
        pbunreal.build_game()
    elif build_val == "package":
        pbunreal.package_binaries()
    elif build_val == "release":
        pbgh.generate_release()
    elif build_val == "inspect":
        pbunreal.inspect_source()
    elif build_val == "inspectall":
        pbunreal.inspect_source(all=True)


def clean_handler(clean_val):
    if clean_val == "workspace":
        if pbtools.wipe_workspace():
            pblog.info("Workspace wipe successful")
        else:
            error_state("Something went wrong while wiping the workspace")

    elif clean_val == "engine":
        if not pbunreal.clean_old_engine_installations():
            error_state(
                "Something went wrong while cleaning old engine installations. You may want to clean them manually.")


def printversion_handler(print_val, repository_val=None):
    if print_val == "latest-engine":
        repository_val = pbunreal.get_versionator_gsuri(repository_val)
        if repository_val is None:
            error_state("--repository <URL> argument should be provided with --print latest-engine command")
        engine_version = pbunreal.get_latest_available_engine_version(str(repository_val))
        if engine_version is None:
            error_state("Could not find latest engine version.")
        print(engine_version, end="")

    elif print_val == "current-engine":
        engine_version = pbunreal.get_engine_version()
        if engine_version is None:
            error_state("Could not find current engine version.")
        print(engine_version, end="")

    elif print_val == "project":
        project_version = pbunreal.get_project_version()
        if project_version is None:
            error_state("Could not find project version.")
        print(project_version, end="")

    elif print_val == "latest-project":
        project_version = pbunreal.get_latest_project_version()
        if project_version is None:
            error_state("Could not find project version.")
        print(project_version, end="")


def autoversion_handler(autoversion_val):
    if pbunreal.project_version_increase(autoversion_val):
        pblog.info("Successfully increased project version")
    else:
        error_state("Error occurred while increasing project version")


def publish_handler(publish_val, dispatch_exec_path):
    if dispatch_exec_path is None:
        error_state(
            "--dispatch argument should be provided for --publish command", hush=True)

    if not pbdispatch.push_build(publish_val, dispatch_exec_path, pbconfig.get('dispatch_config'), pbconfig.get('dispatch_stagedir')):
       error_state("Something went wrong while pushing a new playable build.")


def main(argv):
    parser = argparse.ArgumentParser(description=f"PBSync | PBpy Library Version: {pbpy_version.ver} | PBSync Program Version: {pbsync_version.ver}")

    parser.add_argument("--sync", help="Main command for the PBSync, synchronizes the project with latest changes from the repo, and does some housekeeping",
                        choices=["all", "partial", "binaries", "engineversion", "engine", "force", "ddc"])
    parser.add_argument("--gui", help="Open a GUI page", choices=["sync", "settings"])
    parser.add_argument("--printversion", help="Prints requested version information into console.",
                        choices=["current-engine", "latest-engine", "project"])
    parser.add_argument(
        "--repository", help="gcloud repository url for --printversion latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="Automatic version update for project version",
                        choices=["hotfix", "update", "release"])
    parser.add_argument("--build", help="Does build task according to the specified argument.", choices=["sln", "internal", "game", "source", "package", "release", "inspect", "inspectall"])
    parser.add_argument("--clean", help="""Do cleanup according to specified argument. If engine is provided, old engine installations will be cleared
    If workspace is provided, workspace will be reset with latest changes from current branch (not revertible)""", choices=["engine", "workspace"])
    parser.add_argument("--config", help=f"Path of config XML file. If not provided, ./{default_config_name} is used as default", default=default_config_name)
    parser.add_argument("--publish", help="Publishes a playable build with provided build type",
                        choices=["internal", "playtester"])
    parser.add_argument(
        "--dispatch", help="Required dispatch executable path for --publish command")
    parser.add_argument(
        "--bundle", help="Engine bundle name for --sync engine command. If not provided, engine download will use the default bundle supplied by the config file")
    parser.add_argument(
        "--debugpath", help="If provided, PBSync will run in provided path")
    parser.add_argument(
        "--debugbranch", help="If provided, PBSync will use provided branch as expected branch")

    if len(argv) > 0:
        args = parser.parse_args(argv)
    else:
        pblog.error("At least one valid argument should be passed!")
        pblog.error("Did you mean to launch UpdateProject?")
        input("Press enter to continue...")
        error_state(hush=True, term=True)

    if not (args.debugpath is None):
        # Work on provided debug path
        os.chdir(str(args.debugpath))

    # Parser function object for PBSync config file
    def pbsync_config_parser_func(root):
        config_args_map = {
            'supported_git_version': ('git/version', None),
            'supported_lfs_version': ('git/lfsversion', None),
            'supported_gcm_version': ('git/gcmversion', None),
            'supported_gcm_version_suffix': ('git/gcmversionsuffix', None),
            'gcm_download_suffix': ('git/gcmsuffix', None),
            'expected_branch_name': ('git/expectedbranch', None if args.debugbranch is None else str(args.debugbranch)),
            'git_url': ('git/url', None),
            'branches': ('git/branches/branch', None),
            'checksum_file': ('git/checksumfile', None),
            'log_file_path': ('log/file', None),
            'user_config': ('project/userconfig', None),
            'ci_config': ('project/ciconfig', None),
            'uev_default_bundle': ('versionator/defaultbundle', None),
            'uev_ci_bundle': ('versionator/cibundle', None),
            'engine_base_version': ('project/enginebaseversion', None),
            'uproject_name': ('project/uprojectname', None),
            'defaultgame_path': ('project/defaultgameinipath', None),
            'package_pdbs': ('project/packagepdbs', None),
            'dispatch_config': ('dispatch/config', None),
            'dispatch_drm': ('dispatch/drm', None),
            'dispatch_stagedir': ('dispatch/stagedir', None),
            'resharper_version': ('resharper/version', None),
            'engine_prefix': ('versionator/engineprefix', None),
            'engine_type': ('versionator/enginetype', None),
            'uses_gcs': ('versionator/uses_gcs', None),
            'git_instructions': ('msg/git_instructions', None),
            'support_channel': ('msg/support_channel', None),
        }

        missing_keys = []
        config_map = {}
        for key, val in config_args_map.items():
            tag, override = val
            if override:
                config_map[key] = override
                continue
            el = root.findall(tag)
            if el:
                if len(el) > 1:
                    # if there are multiple keys, use all non-empty ones
                    config_map[key] = [e.text if e.text else "" for e in el]
                else:
                    # if there is just one key, use it
                    config_map[key] = el[0].text if el[0].text else ""
            else:
                missing_keys.append(tag)

        if missing_keys:
            raise KeyError("Missing keys: %s" % ", ".join(missing_keys))

        return config_map

    # Preparation
    config_handler(args.config, pbsync_config_parser_func)
    pblog.setup_logger(pbconfig.get('log_file_path'))

    # Do not process further if we're in an error state
    if pbtools.check_error_state():
        error_state(f"""Repository is currently in an error state. Please fix the issues in your workspace 
        before running PBSync.\nIf you have already fixed the problem, you may remove {pbtools.error_file} from your project folder and 
        run UpdateProject again.""", True)

    # Parse args
    if not (args.gui is None):
        def sync():
            return sync_handler(args.sync, args.repository, args.bundle)
        pbgui.set_default_page(args.gui)
        pbgui.main.run(sync)
    if not (args.sync is None):
        sync_handler(args.sync, args.repository, args.bundle)
    elif not (args.printversion is None):
        printversion_handler(args.printversion, args.repository)
    elif not (args.autoversion is None):
        autoversion_handler(args.autoversion)
    elif not (args.build is None):
        build_handler(args.build)
    elif not (args.clean is None):
        clean_handler(args.clean)
    elif not (args.publish is None):
        publish_handler(args.publish, args.dispatch)
    else:
        pblog.error("At least one valid argument should be passed!")
        pblog.error("Did you mean to launch UpdateProject?")
        input("Press enter to continue...")
        error_state(hush=True)

    pbconfig.shutdown()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if "Scripts" in os.getcwd():
        # Working directory fix for scripts calling PBSync from Scripts folder
        os.chdir("..")
    main(sys.argv[1:])
