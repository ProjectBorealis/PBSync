from functools import partial
from pbpy.pbtools import error_state
import os.path
import os
import sys
import argparse
import webbrowser
import threading
import multiprocessing
import time

from pathlib import Path

from pbpy import pblog
from pbpy import pbgh
from pbpy import pbtools
from pbpy import pbunreal
from pbpy import pbgit
from pbpy import pbconfig
from pbpy import pbpy_version
from pbpy import pbdispatch
from pbpy import pbsteamcmd
from pbpy import pbbutler
from pbpy import pbuac

try:
    import pbsync_version
except ImportError:
    from pbsync import pbsync_version

default_config_name = "PBSync.xml"


def config_handler(config_var, config_parser_func):
    if not pbconfig.generate_config(config_var, config_parser_func):
        # Logger is not initialized yet, so use print instead
        error_state(f"{str(config_var)} config file is not valid or not found. Please check the integrity of the file", hush=True, term=True)


def sync_handler(sync_val: str, repository_val=None):

    sync_val = sync_val.lower()

    if sync_val == "all" or sync_val == "force" or sync_val == "partial":
        pblog.info(f"Executing {sync_val} sync command")
        pblog.info(f"PBpy Library Version: {pbpy_version.ver}")
        pblog.info(f"PBSync Program Version: {pbsync_version.ver}")

        pblog.info("------------------")

        detected_git_version = pbgit.get_git_version()
        supported_git_version = pbconfig.get('supported_git_version')
        needs_git_update = False
        if detected_git_version == supported_git_version:
            pblog.info(f"Current Git version: {detected_git_version}")
        else:
            pblog.warning("Git is not updated to the supported version in your system")
            pblog.warning(f"Supported Git Version: {pbconfig.get('supported_git_version')}")
            pblog.warning(f"Current Git Version: {detected_git_version}")
            needs_git_update = True
            repo = "microsoft/git"
            version = f"v{supported_git_version}"
            if "vfs" in detected_git_version and sys.platform == "win32" or sys.platform == "darwin":
                pblog.info("Auto-updating Git...")
                if sys.platform == "win32":
                    directory = "Saved/PBSyncDownloads"
                    download = f"Git-{supported_git_version}-64-bit.exe"
                    if pbgh.download_release_file(version, download, directory=directory, repo=f"https://github.com/{repo}") != 0:
                        pblog.error("Git auto-update failed, please download and install manually.")
                        webbrowser.open(f"https://github.com/{repo}/releases/download/{version}/{download}")
                    else:
                        download_path = f"Saved\\PBSyncDownloads\\{download}"
                        proc = pbtools.run([download_path])
                        if proc.returncode:
                            pblog.error("Git auto-update failed. Please try manually:")
                            webbrowser.open(f"https://github.com/{repo}/releases/download/{version}/{download}")
                        else:
                            needs_git_update = False
                            # reconfigure credential manager to make sure we have the proper path
                            pbtools.run(["git-credential-manager", "configure"])
                        os.remove(download_path)
                else:
                    proc = pbtools.run([pbgit.get_git_executable(), "update-microsoft-git"])
                    # if non-zero, error out
                    if proc.returncode:
                        pblog.error("Git auto-update failed, please download and install manually.")
                    else:
                        needs_git_update = False
                        input("Launching Git update, please press enter when done installing. ")
            if needs_git_update:
                pblog.error(f"Please install the supported Git version from https://github.com/{repo}/releases/tag/{version}")
                pblog.error(f"Visit {pbconfig.get('git_instructions')} for installation instructions")


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
                    pblog.info("Requesting admin permission to delete bundled Git LFS which is overriding your installed version...")
                    time.sleep(1)
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
            pblog.warning("Git LFS is not updated to the supported version in your system")
            pblog.warning(f"Supported Git LFS Version: {supported_lfs_version}")
            pblog.warning(f"Current Git LFS Version: {detected_lfs_version}")
            version = f"v{supported_lfs_version}"
            needs_git_update = True
            repo = "git-lfs/git-lfs"
            if os.name == "nt":
                pblog.info("Auto-updating Git LFS...")
                directory = "Saved/PBSyncDownloads"
                download = f"git-lfs-windows-{version}.exe"
                result = pbgh.download_release_file(version, download, directory=directory, repo=repo=f"https://github.com/{repo}")
                if result != 0:
                    pblog.error("Git LFS auto-update failed, please download and install manually.")
                    webbrowser.open(f"https://github.com/{repo}/releases/download/{version}/{download}")
                else:
                    download_path = f"Saved\\PBSyncDownloads\\{download}"
                    proc = pbtools.run([download_path])
                    if proc.returncode:
                        pblog.error("Git LFS auto-update failed, please download and install manually.")
                        webbrowser.open(f"https://github.com/{repo}/releases/download/{version}/{download}")
                    else:
                        # install LFS for the user
                        current_drive = Path().resolve()
                        current_drive = current_drive.drive or current_drive.root
                        pbtools.run([pbgit.get_lfs_executable(), "install"], cwd=current_drive)
                        needs_git_update = False
                    os.remove(download_path)

            if needs_git_update:
                pblog.error(f"Please install the supported Git LFS version from https://github.com/{repo}/releases/tag/{version}")

        # check if Git LFS was installed to a different path
        if os.name == "nt" and pbgit.get_lfs_executable() == "git-lfs":
            git_lfs_paths = [path for path in pbtools.whereis("git-lfs")]
            if len(git_lfs_paths) > 1:
                index = 0
                main_lfs_path = git_lfs_paths[0]
                for git_lfs_path in git_lfs_paths:
                    if supported_lfs_version == pbgit.get_lfs_version(git_lfs_path):
                        if index != 0:
                            pblog.info("Requesting admin permission to move installed Git LFS which is being overridden...")
                            time.sleep(1)
                            move_cmdline = ["cmd.exe", "/c", "MOVE", "/Y", f'"{git_lfs_path}"', f'"{main_lfs_path}"']
                            try:
                                ret = pbuac.runAsAdmin(move_cmdline)
                            except OSError:
                                pblog.error("User declined permission. Automatic move failed.")
                                pblog.error(f"Git LFS is installed to a different location, overriding your installed version. Please install Git LFS to {main_lfs_path.parents[1]}.")
                                error_state()
                        break
                    index += 1


        detected_gcm_version = pbgit.get_gcm_version()
        supported_gcm_version_raw = pbconfig.get('supported_gcm_version')
        supported_gcm_version = f"{supported_gcm_version_raw}"
        if detected_gcm_version == supported_gcm_version:
            pblog.info(f"Current Git Credential Manager version: {detected_gcm_version}")
        else:
            pblog.warning("Git Credential Manager is not updated to the supported version in your system")
            pblog.warning(f"Supported Git Credential Manager Version: {supported_gcm_version}")
            pblog.warning(f"Current Git Credential Manager Version: {detected_gcm_version}")
            needs_git_update = True
            if detected_gcm_version.startswith("diff"):
                # remove the old credential helper (it may get stuck, and GCM won't be able to install)
                pbtools.run_with_combined_output([pbgit.get_git_executable(), "config", "--unset-all", "credential.helper"])
                pbtools.run_with_combined_output([pbgit.get_git_executable(), "config", "--global", "--unset-all", "credential.helper"])
                exe_location = detected_gcm_version.split(".", 1)[1]
                # if they actually have a Windows program installed, inform them.
                if exe_location.endswith(".exe"):
                    pblog.error(f"It seems like you have another Git credential helper installed at: {exe_location}.")
                    pblog.error("Please uninstall this and Git Credential Manager if you have it in \"Add or remove programs\" and then install Git Credential Manager again.")
                else:
                    pblog.error("Please uninstall Git Credential Manager if you have it in \"Add or remove programs\" and then install Git Credential Manager again.")
            else:
                if os.name == "nt":
                    pblog.info("Auto-updating Git Credential Manager...")
                    version = f"v{supported_gcm_version}"
                    directory = "Saved/PBSyncDownloads"
                    download = f"gcm-win-x86-{supported_gcm_version_raw}.exe"
                    repo = "https://github.com/git-ecosystem/git-credential-manager"
                    if pbgh.download_release_file(version, download, directory=directory, repo=f"https://github.com/{repo}") != 0:
                        pblog.error("Git Credential Manager auto-update failed, please download and install manually.")
                        webbrowser.open(f"https://github.com/{repo}/releases/download/{version}/{download}")
                    else:
                        download_path = f"Saved\\PBSyncDownloads\\{download}"
                        proc = pbtools.run([download_path])
                        if proc.returncode:
                            pblog.error("Git Credential Manager auto-update failed, please download and install manually.")
                            webbrowser.open(f"https://github.com/{repo}/releases/download/{version}/{download}")
                        else:
                            # reconfigure credential manager to make sure we have the proper path
                            pbtools.run(["git-credential-manager", "configure"])
                            needs_git_update = False
                        os.remove(download_path)

            if not needs_git_update:
                # this handles a case where GCM is installed by Git itself, and blocks GCM from installing the new one
                needs_git_update = pbgit.get_gcm_version() != supported_gcm_version
                if needs_git_update:
                    # remove the old credential helper (it may get stuck, and GCM won't be able to install)
                    pbtools.run_with_combined_output([pbgit.get_git_executable(), "config", "--unset-all", "credential.helper"])
                    pbtools.run_with_combined_output([pbgit.get_git_executable(), "config", "--global", "--unset-all", "credential.helper"])
                    pblog.error("Git Credential Manager failed due to an installation conflict, please launch UpdateProject again to finalize the installation.")
            else:
                pblog.error("Please install the supported Git Credential Manager version from https://github.com/GitCredentialManager/git-credential-manager/releases")

        if needs_git_update:
            error_state()

        pblog.info("------------------")

        # Check our remote connection before doing anything
        remote_state, remote_url = pbgit.check_remote_connection()
        if not remote_state:
            error_state(
                f"Remote connection was not successful. Please verify that you have an internet connection. Current git remote URL: {remote_url}")
        else:
            pblog.info("Remote connection is up")

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

        # undo single branch clone
        if not is_ci:
            pbtools.run([pbgit.get_git_executable(), "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"])

        # Execute synchronization part of script if we're on the expected branch, or force sync is enabled
        if sync_val == "force" or pbgit.is_on_expected_branch():
            if partial_sync:
                pbtools.maintain_repo()
            else:
                pbtools.resolve_conflicts_and_pull()

                pblog.info("------------------")

            project_version = pbunreal.get_project_version()
            is_custom_version = pbunreal.is_using_custom_version()
            needs_binaries_pull = pbgh.is_pull_binaries_required()
            if project_version is not None:
                if is_custom_version:
                    pblog.info(f"User selected project version: {project_version}")
                else:
                    pblog.info(f"Current project version: {project_version}")
            elif needs_binaries_pull:
                error_state(f"Something went wrong while fetching project version. Please request help in {pbconfig.get('support_channel')}.")

            checksum_json_path = pbconfig.get("checksum_file")
            if is_custom_version:
                # checkout old checksum file from tag
                pbgit.sync_file(checksum_json_path, project_version)

            if needs_binaries_pull:
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
        elif pbconfig.get_user_config().getboolean("project", "autosync", fallback=True):
            pbtools.resolve_conflicts_and_pull()
        else:
            pblog.info(f"Current branch does not need auto synchronization: {pbgit.get_current_branch_name()}.")
            pbtools.maintain_repo()

        symbols_needed = pbunreal.is_versionator_symbols_enabled()
        pbunreal.clean_binaries_folder(not symbols_needed)

        configured_branches = pbconfig.get("branches")
        should_unlock_unmodified = pbgit.get_current_branch_name() in configured_branches
        fix_attr_thread = threading.Thread(target=pbgit.fix_lfs_ro_attr, args=(should_unlock_unmodified,))
        fix_attr_thread.start()

        pblog.info("------------------")

        pblog.info("Checking for engine updates...")
        uproject_file = pbconfig.get('uproject_name')
        if pbgit.sync_file(uproject_file) != 0:
            error_state(f"Something went wrong while updating the uproject file. Please request help in {pbconfig.get('support_channel')}.")

        engine_version = pbunreal.get_engine_version_with_prefix()
        if engine_version is not None:
            pblog.info("Registering current engine build if it exists. Otherwise, the build will be downloaded...")

            bundle_name = pbunreal.get_bundle()

            if pbunreal.download_engine(bundle_name, symbols_needed):
                pblog.info(f"Engine build {bundle_name}-{engine_version} successfully registered")
            else:
                error_state(f"Something went wrong while registering engine build {bundle_name}-{engine_version}. Please request help in {pbconfig.get('support_channel')}.")

            # Clean old engine installations
            if pbconfig.get_user_config().getboolean("ue4v-user", "clean", fallback=True):
                if pbunreal.clean_old_engine_installations():
                    pblog.info("Successfully cleaned old engine installations.")
                else:
                    pblog.warning("Something went wrong while cleaning old engine installations. You may want to clean them manually.")

        binaries_mode = pbgit.get_binaries_mode()
        if binaries_mode == "build":
            pbunreal.generate_project_files()
            pbunreal.build_source(for_distribution=False)

        pblog.info("------------------")

        pblog.info("Updating Unreal configuration settings")
        pbunreal.update_source_control()

        pbunreal.sync_ddc_vt()

        pblog.info("Finishing LFS locks cleanup...")
        fix_attr_thread.join()
        pblog.info("Finished LFS locks cleanup.")

        launch_pref = pbconfig.get_user("project", "launch", "none") if is_ci else pbconfig.get_user("project", "launch", "editor")
        if launch_pref == "vs":
            os.startfile(pbunreal.get_sln_path())
        elif launch_pref == "rider":
            rider_bin = pbtools.get_one_line_output(["echo", "%Rider for Unreal Engine%"])
            rider_bin = rider_bin.replace(";", "")
            rider_bin = rider_bin.replace("\"", "")
            pbtools.run_non_blocking(f'"{rider_bin}\\rider64.exe" "{str(pbunreal.get_sln_path().resolve())}"')
        elif pbunreal.is_ue_closed():
            if launch_pref == "editor":
                extra_args = pbconfig.get_user("project", "editor_args", default="").split()
                if extra_args:
                    launch_args = [pbunreal.get_editor_path(), path]
                    launch_args.extend(extra_args)
                    pbtools.run_non_blocking_ex(launch_args)
                else:
                    launched_editor = False
                    if pbunreal.check_ue_file_association():
                        uproject_file = pbconfig.get('uproject_name')
                        path = str(Path(uproject_file).resolve())
                        try:
                            os.startfile(path)
                            launched_editor = True
                        except OSError:
                            # files are associated, but the executable is not found
                            pass
                        except NotImplementedError:
                            if sys.platform.startswith('linux'):
                                pbtools.run_non_blocking(f"xdg-open {path}")
                                launched_editor = True

                    if not launched_editor:
                        pblog.warning(f"PBSync failed to find a valid file association to launch the editor, and will attempt to launch the editor directly as a workaround.")
                        pbtools.run_non_blocking_ex([pbunreal.get_editor_path(), path])
                        pblog.warning(f"If PBSync failed to launch the directly directly, please launch {uproject_file} manually for now.")
                        error_state(f"For a permanent fix, try clearing out file associations for the .uproject file type and launching PBSync again. Please get help in {pbconfig.get('support_channel')} if the issue continues.")

            # TODO
            #elif launch_pref == "debug":
            #    pbtools.run_non_blocking(f"\"{str(pbunreal.get_devenv_path())}\" \"{str(pbunreal.get_sln_path())}\" /DebugExe \"{str(pbunreal.get_editor_path())}\" \"{str(pbunreal.get_uproject_path())}\" -skipcompile")


    elif sync_val == "engineversion":
        repository_val = pbunreal.get_versionator_gsuri(repository_val)
        if repository_val is None:
                error_state("--repository <URL> argument should be provided with --sync engineversion command")
        engine_version = pbunreal.get_latest_available_engine_version(str(repository_val))
        if engine_version is None:
            error_state("Error while fetching latest engine version")
        if not pbunreal.set_engine_version(engine_version):
            error_state("Error while updating engine version in .uproject file")
        pblog.info(f"Successfully changed engine version as {str(engine_version)}")

    elif sync_val == "ddc":
        pbunreal.sync_ddc_vt()

    elif sync_val == "binaries":
        project_version = pbunreal.get_project_version()
        ret = pbgh.pull_binaries(project_version, True)
        if ret == 0:
            pblog.info(f"Binaries for {project_version} pulled and extracted successfully")
        else:
            error_state(f"Failed to pull binaries for {project_version}")

    elif sync_val == "engine":
        # Pull engine build with ueversionator and register it
        bundle_name = pbunreal.get_bundle()

        engine_version = pbunreal.get_engine_version_with_prefix()
        symbols_needed = pbunreal.is_versionator_symbols_enabled()
        if engine_version is not None:
            if pbunreal.download_engine(bundle_name, symbols_needed):
                pblog.info(f"Engine build {bundle_name}-{engine_version} successfully registered")
                if pbconfig.get("is_ci"):
                    pbunreal.clean_old_engine_installations(keep=3)
            else:
                error_state(f"Something went wrong while registering engine build {bundle_name}-{engine_version}")


build_hooks = {
    "sln": pbunreal.generate_project_files,
    "source": pbunreal.build_source,
    "debuggame": partial(pbunreal.build_game, "DebugGame"),
    "development": partial(pbunreal.build_game, "Development"),
    "internal": partial(pbunreal.build_game, "Test"),
    "game": pbunreal.build_game,
    "installedbuild": pbunreal.build_installed_build,
    "package": pbunreal.package_binaries,
    "release": pbgh.generate_release,
    "inspect": pbunreal.inspect_source,
    "inspectall": partial(pbunreal.inspect_source, all=True),
    "fillddc": pbunreal.fill_ddc,
    "s3ddc": pbunreal.upload_cloud_ddc,
    "ddc": pbunreal.generate_ddc_data,
    "clearcook": pbunreal.clear_cook_cache,
}


def build_handler(build_val):
    for build_action in build_val:
        build_func = build_hooks.get(build_action)
        if build_func:
            build_func()


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


PUBLISHERS = {
    "dispatch": lambda publish_val, pubexe: pbdispatch.publish_build(publish_val, pubexe, pbconfig.get('publish_stagedir'), pbconfig.get('dispatch_config')),
    "steamcmd": lambda publish_val, pubexe: pbsteamcmd.publish_build(publish_val, pubexe, pbconfig.get('publish_stagedir'), pbconfig.get("steamcmd_script")),
    "butler": lambda publish_val, pubexe: pbbutler.publish_build(publish_val, pubexe, pbconfig.get('publish_stagedir'), pbconfig.get('butler_project'), pbconfig.get('butler_manifest')),
}


def publish_handler(publish_val):
    publishers = pbconfig.get('publish_publishers')
    for publisher in publishers:
        fn = PUBLISHERS.get(publisher)
        if not fn:
            error_state(f"Unknown publisher: {publisher}")
        result = fn(publish_val.lower(), publisher)
        if result != 0:
            error_state(f"Something went wrong while publishing a new build. Error code {result}")


def main(argv):
    parser = argparse.ArgumentParser(description=f"PBSync | PBpy Library Version: {pbpy_version.ver} | PBSync Program Version: {pbsync_version.ver}")

    parser.add_argument("--sync", help="Main command for the PBSync, synchronizes the project with latest changes from the repo, and does some housekeeping",
                        choices=["all", "partial", "binaries", "engineversion", "engine", "force", "ddc"], const="all", nargs="?")
    parser.add_argument("--printversion", help="Prints requested version information into console.",
                        choices=["current-engine", "latest-engine", "project"])
    parser.add_argument(
        "--repository", help="gcloud repository url for --printversion latest-engine and --sync engine commands")
    parser.add_argument("--autoversion", help="Automatic version update for project version",
                        choices=["patch", "minor", "major"])
    parser.add_argument("--build", help="Does build task according to the specified argument.", action='append', choices=list(build_hooks.keys()))
    parser.add_argument("--clean", help="""Do cleanup according to specified argument. If engine is provided, old engine installations will be cleared
    If workspace is provided, workspace will be reset with latest changes from current branch (not revertible)""", choices=["engine", "workspace"])
    parser.add_argument("--config", help=f"Path of config XML file. If not provided, ./{default_config_name} is used as default", default=default_config_name)
    parser.add_argument("--publish", help="Publishes a playable build with provided build type", const="default", nargs="?")
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
            'supported_git_version': ('git/version', None, None, True),
            'supported_lfs_version': ('git/lfsversion', None, None, True),
            'supported_gcm_version': ('git/gcmversion', None, None, True),
            'expected_branch_names': ('git/expectedbranch', None if args.debugbranch is None else [str(args.debugbranch)], ["main"], False),
            'git_url': ('git/url', None, None, True),
            'branches': ('git/branches/branch', None, ["main"], False),
            'log_file_path': ('log/file', None, "pbsync_log.txt", True),
            'user_config': ('project/userconfig', None, ".user-sync", True),
            'ci_config': ('project/ciconfig', None, ".ci-sync", True),
            'uev_default_bundle': ('versionator/defaultbundle', None, "editor", True),
            'uev_ci_bundle': ('versionator/cibundle', None, "engine", True),
            'engine_base_version': ('project/enginebaseversion', None, "", True),
            'uproject_name': ('project/uprojectname', None, None, True),
            'defaultgame_path': ('project/defaultgameinipath', None, "Config/DefaultGame.ini", True),
            'package_pdbs': ('project/packagepdbs', None, False, True),
            'ddc_key': ('project/ddckey', None, "", True),
            'publish_publishers': ('publish/publisher', None, [""], False),
            'publish_stagedir': ('publish/stagedir', None, "Saved/StagedBuilds", True),
            'dispatch_config': ('dispatch/config', None, "", True),
            'butler_project': ('butler/project', None, "", True),
            'butler_manifest': ('butler/manifest', None, "", True),
            'steamcmd_script': ('steamcmd/script', None, "", True),
            'resharper_version': ('resharper/version', None, "", True),
            'engine_prefix': ('versionator/engineprefix', None, "", True),
            'engine_type': ('versionator/enginetype', None, None, True),
            'uses_gcs': ('versionator/uses_gcs', None, False, True),
            'uses_longtail': ('versionator/uses_longtail', None, False, True),
            'git_instructions': ('msg/git_instructions', None, "https://github.com/ProjectBorealis/PBCore/wiki/Prerequisites", True),
            'support_channel': ('msg/support_channel', None, None, True),
        }

        missing_keys = []
        config_map = {}
        for key, val in config_args_map.items():
            tag, override, default, is_single = val
            if override is not None:
                config_map[key] = override
                continue
            el = root.findall(tag)
            if el:
                el = [e.text if e.text else "" for e in root.findall(tag)]
                size = len(el)
                optional = size > 0
                if size == 1 and is_single:
                    # if there is just one key, use it
                    el = el[0]
            else:
                el = default
                optional = default is not None
            if el or optional:
                config_map[key] = el
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

    if len(sys.argv) < 2:
        pblog.error("At least one valid argument should be passed!")
        pblog.error("Did you mean to launch UpdateProject?")
        input("Press enter to continue...")
        error_state(hush=True)

    # Parse args
    if not (args.printversion is None):
        printversion_handler(args.printversion, args.repository)
    if not (args.clean is None):
        clean_handler(args.clean)
    if not (args.sync is None):
        sync_handler(args.sync, args.repository)
    if not (args.autoversion is None):
        autoversion_handler(args.autoversion)
    if not (args.build is None):
        build_handler(args.build)
    if not (args.publish is None):
        publish_handler(args.publish)

    pbconfig.shutdown()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if "Scripts" in os.getcwd():
        # Working directory fix for scripts calling PBSync from Scripts folder
        os.chdir("..")
    main(sys.argv[1:])
