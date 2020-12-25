import subprocess
import re
from shutil import move
from shutil import rmtree
from shutil import disk_usage
from os import remove
from functools import lru_cache
from urllib.parse import urlparse
from pathlib import Path
from gslib.command_runner import CommandRunner
from gslib.commands.cp import CpCommand
from gslib.commands.rsync import RsyncCommand
import os
import json
import glob
import pathlib
import configparser
import contextlib

import gslib

from pbpy import pbconfig
from pbpy import pbtools
from pbpy import pblog
from pbpy import pbgit
from pbpy import pbuac

# Those variable values are not likely to be changed in the future, it's safe to keep them hardcoded
ue4v_prefix = "ue4v:"
uplugin_ext = ".uplugin"
uproject_ext = ".uproject"
uplugin_version_key = "VersionName"
uproject_version_key = "EngineAssociation"
project_version_key = "ProjectVersion="
ddc_folder_name = "DerivedDataCache"
ue4_editor_relative_path = "Engine/Binaries/Win64/UE4Editor.exe"
# TODO: make these config variables
engine_installation_folder_regex = r"[0-9].[0-9]{2}.*-PB-[0-9]{8}"
engine_version_prefix = "PB"
p4merge_path = ".github/p4merge/p4merge.exe"


def get_plugin_version(plugin_name):
    plugin_root = f"Plugins/{plugin_name}"
    for uplugin_path in glob.glob(f"{plugin_root}/*{uplugin_ext}"):
        with open(uplugin_path) as uplugin_file:
            data = json.load(uplugin_file)
            version = data[uplugin_version_key]
            # Some plugins have strange versions with only major and minor versions, add patch version for
            # compatibility with package managers
            if version.count('.') == 1:
                version += ".0"
            return version
    return None


def get_user_version():
    return pbconfig.get_user("project", "version", "latest")


def is_using_custom_version():
    return get_user_version() != "latest"


def get_project_version():
    # first check if the user selected their own version
    user_version = get_user_version()
    if user_version != "latest":
        return user_version

    try:
        with open(pbconfig.get('defaultgame_path')) as ini_file:
            for ln in ini_file:
                if ln.startswith(project_version_key):
                    return ln.replace(project_version_key, '').rstrip()
    except Exception as e:
        pblog.exception(str(e))
        return None
    return None


def set_project_version(version_string):
    temp_path = "tmpProj.txt"
    # Create a temp file, do the changes there, and replace it with actual file
    try:
        with open(pbconfig.get('defaultgame_path')) as ini_file:
            with open(temp_path, "wt") as fout:
                for ln in ini_file:
                    if project_version_key in ln:
                        fout.write(f"ProjectVersion={version_string}\n")
                    else:
                        fout.write(ln)
        remove(pbconfig.get('defaultgame_path'))
        move(temp_path, pbconfig.get('defaultgame_path'))
    except Exception as e:
        pblog.exception(str(e))
        return False
    return True


def set_engine_version(version_string):
    temp_path = "tmpEng.txt"
    try:
        # Create a temp file, do the changes there, and replace it with actual file
        with open(pbconfig.get('uproject_name')) as uproject_file:
            with open(temp_path, "wt") as fout:
                for ln in uproject_file:
                    if uproject_version_key in ln:
                        fout.write(f"\t\"{uproject_version_key}\": \"{ue4v_prefix}{version_string}\",\n")
                    else:
                        fout.write(ln)
        remove(pbconfig.get('uproject_name'))
        move(temp_path, pbconfig.get('uproject_name'))
    except Exception as e:
        pblog.exception(str(e))
        return False
    return True


def project_version_increase(increase_type):
    increase_type = increase_type.lower()
    project_version = get_project_version()
    if project_version is None:
        return False

    # Split hotfix, stable and release versions into an array
    version_split = project_version.split('.')

    if len(version_split) != 3:
        print("Incorrect project version detected")
        return False
    if increase_type == "hotfix":
        new_version = f"{version_split[0] }.{version_split[1]}.{str(int(version_split[2]) + 1)}"
    elif increase_type == "stable":
        new_version = f"{version_split[0] }.{str(int(version_split[1]) + 1)}.0"
    elif increase_type == "public":
        new_version = f"{str(int(version_split[2]) + 1)}.0.0"
    else:
        return False

    print(f"Project version will be increased to {new_version}")
    return set_project_version(new_version)


@lru_cache()
def get_engine_prefix() -> str:
    return f"{pbconfig.get('engine_base_version')}-{engine_version_prefix}"


@lru_cache()
def get_engine_version():
    try:
        with open(pbconfig.get('uproject_name')) as uproject_file:
            data = json.load(uproject_file)
            engine_association = str(data[uproject_version_key])
            build_version = engine_association.replace(f"{ue4v_prefix}{get_engine_prefix()}-", "")

            if "}" in build_version:
                # Means we're using local build version in .uproject file
                return None

            return build_version
    except Exception as e:
        pblog.exception(str(e))
        return None


@lru_cache()
def get_engine_version_with_prefix():
    engine_ver_number = get_engine_version()
    if engine_ver_number is not None:
        return f"{get_engine_prefix()}-{engine_ver_number}"
    return None


def get_engine_install_root():
    root = pbconfig.get_user("ue4v-user", "download_dir")
    if root is None:
        curdir = Path().resolve()

        if pbconfig.get("is_ci"):
            if os.name == "nt":
                directory = (Path(curdir.anchor) / "ue4").resolve()
            else:
                directory = (curdir.parent / "ue4").resolve()
            directory.mkdir(exist_ok=True)
            return str(directory)

        print("======================================================================")
        print("| A custom UE4 engine build needs to be downloaded for this project. |")
        print("|  These builds can be quite large. Lots of disk space is required.  |")
        print("======================================================================\n")
        print(f">>>>> Project path: {curdir}\n")
        print("Which directory should these engine downloads be stored in?\n")

        options = []

        # parent directory
        options.append(curdir.parent)

        # home directory
        options.append(Path.home())

        # drive
        if os.name == "nt":
            options.append(Path(curdir.anchor))

        # go into ue4 folder
        options = [(path / 'ue4').resolve() for path in options]

        # remove duplicates
        options = list(dict.fromkeys(options))

        # add custom option
        custom = "custom location"
        options.append(custom)

        for i, option in enumerate(options):
            print(f"{i + 1}) {option}")

        directory = None
        while True:
            response = input(f"\nSelect an option (1-{len(options)}) and press enter: ")
            try:
                choice = int(response) - 1
                if choice >= 0 and choice < len(options):
                    directory = options[choice]
                    if directory == custom:
                        try:
                            response = input("\nCustom location: ")
                            directory = Path(response.strip()).resolve()
                            try:
                                directory.relative_to(curdir)
                                relative = True
                            except ValueError:
                                relative = False
                            if relative:
                                print("download directory cannot reside in the project directory")
                                continue
                        except Exception as e:
                            pblog.exception(str(e))
                            directory = None

                    if directory:
                        try:
                            directory.mkdir(exist_ok=True)
                            break
                        except Exception as e:
                            pblog.exception(str(e))
                            continue
            except ValueError:
                print("\n")

            pblog.error(f"Invalid option {response}. Try again:\n")
        if directory:
            root = str(directory)
            pbconfig.get_user_config()["ue4v-user"]["download_dir"] = root
    return root


def get_latest_available_engine_version(bucket_url):
    output = pbtools.get_combined_output(["gsutil", "ls", bucket_url])
    build_type = pbconfig.get("ue4v_default_bundle")
    if pbconfig.get("is_ci"):
        # We should get latest version of ciengine instead
        build_type = pbconfig.get("ue4v_ci_bundle")

    # e.g, "engine-4.24-PB"
    regex_prefix = f"{build_type}-{pbconfig.get('engine_base_version')}-{engine_version_prefix}"
    versions = re.findall(regex_prefix + "-[0-9]{8}", output)
    if len(versions) == 0:
        return None
    # Find the latest version by sorting
    versions.sort()

    # Strip the build type prefix back
    result = str(versions[len(versions) - 1])
    result = result.replace(f"{build_type}-", '')
    return result.rstrip()


def check_ue4_file_association():
    if os.name == 'nt':
        file_assoc_result = pbtools.get_combined_output(["assoc", uproject_ext])
        return "Unreal.ProjectFile" in file_assoc_result
    else:
        return True


def check_ddc_folder_created():
    ddc_path = os.path.join(os.getcwd(), ddc_folder_name)
    return os.path.isdir(ddc_path)


def generate_ddc_data():
    pblog.info("Generating DDC data, please wait... (This may take up to one hour only for the initial run)")
    current_version = get_engine_version_with_prefix()
    if current_version is not None:
        engine_install_root = get_engine_install_root()
        installation_dir = os.path.join(engine_install_root, current_version)
        if os.path.isdir(installation_dir):
            ue_editor_executable = os.path.join(
                installation_dir, ue4_editor_relative_path)
            if os.path.isfile(ue_editor_executable):
                err = pbtools.run([str(ue_editor_executable), str(pathlib.Path(pbconfig.get('uproject_name')).resolve()), "-run=DerivedDataCache", "-fill"]).returncode
                if err == 0:
                    pblog.info(f"DDC generate command has exited with {err}")
                else:
                    pblog.error(f"DDC generate command has exited with {err}")
                if not check_ddc_folder_created():
                    pbtools.error_state(
                        "DDC folder doesn't exist. Please get support from #tech-support")
                pblog.info("DDC data successfully generated!")
                return
        pbtools.error_state(
        "Engine installation not found. Please get support from #tech-support")  
    pbtools.error_state(
    "Error occurred while reading project version for DDC data generation. Please get support from #tech-support")


def clean_old_engine_installations(keep=1):
    current_version = get_engine_version_with_prefix()
    p = re.compile(engine_installation_folder_regex)
    if current_version is not None:
        engine_install_root = get_engine_install_root()
        if engine_install_root is not None and os.path.isdir(engine_install_root):
            folders = os.listdir(engine_install_root)
            for i in range(0, len(folders) - keep):
                folder = folders[i]
                # Do not remove folders if they do not match with installation folder name pattern
                # Also do not remove files. Only remove folders
                full_path = os.path.join(engine_install_root, folder)
                if folder != current_version and p.match(folder) is not None and os.path.isdir(full_path):
                    print(f"Removing old engine installation: {str(full_path)}...")
                    try:
                        rmtree(full_path, ignore_errors=True)
                        print("Removal was successful!")
                    except Exception as e:
                        pblog.exception(str(e))
                        print(f"Something went wrong while removing engine folder {str(full_path)}. Please try removing it manually.")
            return True

    return False


@lru_cache()
def get_versionator_gsuri(fallback=None):
    try:
        ue4v_config = configparser.ConfigParser()
        ue4v_config.read(".ue4versionator")
        baseurl = ue4v_config.get("ue4versionator", "baseurl", fallback=fallback)
        if baseurl:
            domain = urlparse(baseurl).hostname
            return f"gs://{domain}/"
    except Exception as e:
        pblog.exception(str(e))
    return None


@lru_cache()
def is_versionator_symbols_enabled():
    symbols = pbconfig.get_user_config().getboolean("ue4v-user", "symbols", fallback=None)
    if symbols is not None:
        return symbols

    if pbconfig.get("is_ci"):
        return False

    # Symbols configuration variable is not on the file, let's add it
    response = input("Do you want to download debugging symbols for accurate crash logging? You can change this setting later in the .ue4v-user config file. [y/N] ")
    if len(response) > 0 and response[0].lower() == "y":
        pbconfig.get_user_config()["ue4v-user"]["symbols"] = "true"
        return True
    else:
        pbconfig.get_user_config()["ue4v-user"]["symbols"] = "false"
        return False


def get_bundle_verification_file(bundle_name):
    if bundle_name and "engine" in bundle_name:
        return "Engine/Binaries/Win64/UE4Game."
    else:
        return "Engine/Binaries/Win64/UE4Editor."


def download_engine(bundle_name=None, download_symbols=False):
    required_free_gb = 7
    
    if download_symbols:
        required_free_gb += 23

    required_free_space = required_free_gb * 1000 * 1000 * 1000

    is_ci = pbconfig.get("is_ci")

    root = get_engine_install_root()
    if root is not None:
        if not pbconfig.get("is_ci") and os.path.isdir(root):
            total, used, free = disk_usage(root)

            if free < required_free_space:
                pblog.warning("Not enough free space. Cleaning old engine installations before download.")
                clean_old_engine_installations()
                total, used, free = disk_usage(root)
                if free < required_free_space:
                    pblog.error(f"You do not have enough available space to install the engine. Please free up space on f{pathlib.Path(root).anchor}")
                    available_gb = int(free / (1000 * 1000 * 1000))
                    pblog.error(f"Available space: {available_gb}GB")
                    pblog.error(f"Total install size: {required_free_gb}GB")
                    pblog.error(f"Required space: {int((free - required_free_space) / (1000 * 1000 * 1000))}")
                    pbtools.error_state()

        # create install dir if doesn't exist
        os.makedirs(root, exist_ok=True)

        verification_file = get_bundle_verification_file(bundle_name)
        version = get_engine_version_with_prefix()
        base_path = pathlib.Path(root) / pathlib.Path(version)
        symbols_path = base_path / pathlib.Path(verification_file + "pdb")
        needs_symbols = download_symbols and not symbols_path.exists()
        exe_path = base_path / pathlib.Path(verification_file + "exe")
        needs_exe = not exe_path.exists()
        try:
            legacy_archives = pbconfig.get_user_config().getboolean("ue4v-user", "legacy", fallback=False) or int(get_engine_version()) <= 20201030
        except:
            legacy_archives = True

        legacy_archives = True

        if not legacy_archives:
            pblog.success("Using new remote sync method for engine update.")

        if needs_exe or needs_symbols:
            # Use gsutil to download the files efficiently
            if (gslib.utils.parallelism_framework_util.CheckMultiprocessingAvailableAndInit().is_available):
                # These setup methods must be called, and, on Windows, they can only be
                # called from within an "if __name__ == '__main__':" block.
                gslib.command.InitializeMultiprocessingVariables()
                gslib.boto_translation.InitializeMultiprocessingVariables()
            else:
                gslib.command.InitializeThreadingVariables()
            command_runner = CommandRunner(command_map={
                "cp": CpCommand,
                "rs": RsyncCommand
            })
            patterns = []
            if needs_exe and needs_symbols:
                if legacy_archives:
                    patterns.append(f"{bundle_name}*")
                else:
                    patterns.append(f"{bundle_name}")
                    patterns.append(f"{bundle_name}-symbols")
            elif needs_symbols:
                patterns.append(f"{bundle_name}-symbols")
            else:
                patterns.append(f"{bundle_name}")
            patterns = [f"{pattern}-{version}.7z" if legacy_archives else "/" for pattern in patterns]
            gcs_bucket = get_versionator_gsuri()
            for pattern in patterns:
                gcs_uri = f"{gcs_bucket}{pattern}"
                dst = f"file://{root}"
                command_runner.RunNamedCommand('cp' if legacy_archives else 'rs', args=["-n", gcs_uri, dst], collect_analytics=False, skip_update_check=True, parallel_operations=needs_exe and needs_symbols)

    # Extract and register with ue4versionator
    # TODO: handle registration
    if False and root is not None:
        if os.name == "nt":
            try:
                import winreg
                engine_ver = f"{bundle_name}-{version}"
                engine_id = f"{ue4v_prefix}{engine_ver}"
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Epic Games\Unreal Engine\Builds", access=winreg.KEY_SET_VALUE) as key:
                    # This does not work for some reason.
                    winreg.SetValueEx(key, engine_id, 0, winreg.REG_SZ, str(os.path.join(root, engine_ver)))
            except Exception as e:
                pblog.exception(str(e))
                return False
    else:
        command_set = ["ue4versionator.exe"]

        command_set.append("-assume-valid")

        if bundle_name is not None:
            command_set.append("-bundle")
            command_set.append(str(bundle_name))

        if is_ci:
            # If we're CI, write our environment variable to user config
            user_config = pbconfig.get_user_config()
            for section in user_config.sections():
                for key in list(user_config[section].keys()):
                    val = pbconfig.get_user(section, key)
                    if val:
                        user_config[section][key] = val
                    else:
                        user_config.remove_option(section, key)
            with open(pbconfig.get('ue4v_user_config'), 'w') as user_config_file:
                pbconfig.get_user_config().write(user_config_file)

        if pbtools.run(command_set).returncode != 0:
            return False

    # if not CI, run the setup tasks
    if root is not None and not is_ci and needs_exe:
        pblog.info("Installing Unreal Engine prerequisites")
        prereq_path = base_path / pathlib.Path("Engine/Extras/Redist/en-us/UE4PrereqSetup_x64.exe")
        pbtools.run([str(prereq_path), "/quiet"])
        pblog.info("Registering Unreal Engine file associations")
        selector_path = base_path / pathlib.Path("Engine/Binaries/Win64/UnrealVersionSelector-Win64-Shipping.exe")
        cmdline = [str(selector_path), "/fileassociations"]
        if not pbuac.isUserAdmin():
            pbuac.runAsAdmin(cmdline)
        else:
            pbtools.run(cmdline)
        # generate project files for developers
        current_branch = pbgit.get_current_branch_name()
        expected_branch = pbconfig.get("expected_branch_name")
        is_on_expected_branch = current_branch == expected_branch
        if not is_on_expected_branch:
            uproject = str(pathlib.Path(pbconfig.get("uproject_name")).resolve())
            pbtools.run([selector_path, "/projectfiles", uproject])

    return True


@contextlib.contextmanager
def ue4_config(path):
    config = configparser.ConfigParser(allow_no_value=True, delimiters=("=",))
    # case sensitive
    config.optionxform = lambda option: option
    config.read(path)
    try:
        yield config
    finally:
        with open(path, 'w') as ini_file:
            config.write(ini_file, space_around_delimiters=False)


def update_source_control():
    with ue4_config("Saved/Config/Windows/SourceControlSettings.ini") as source_control_config:
        source_control_config["SourceControl.SourceControlSettings"]["Provider"] = pbconfig.get_user("project", "provider", "Git LFS 2")
        git_lfs_2 = source_control_config["GitSourceControl.GitSourceControlSettings"]
        binary_path = pbgit.get_git_executable()
        if binary_path != "git":
            git_lfs_2["BinaryPath"] = binary_path
        else:
            git_paths = [path for path in pbtools.whereis("git") if "cmd" in path.parts]
            if len(git_paths) > 0:
                git_lfs_2["BinaryPath"] = str(git_paths[0].resolve())
        git_lfs_2["UsingGitLfsLocking"] = "True"
        username, _ = pbgit.get_credentials()
        git_lfs_2["LfsUserName"] = username
    with ue4_config("Saved/Config/Windows/EditorPerProjectUserSettings.ini") as editor_config:
        p4merge = str(pathlib.Path(p4merge_path).resolve())
        editor_config["/Script/UnrealEd.EditorLoadingSavingSettings"]["TextDiffToolPath"] = f"(FilePath=\"{p4merge}\")"
