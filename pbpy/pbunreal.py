import itertools
import re
import os
import json
import glob
import configparser
import contextlib
import urllib.request
import platform
import zipfile

from shutil import move
from shutil import rmtree
from shutil import disk_usage
from functools import lru_cache
import shutil
from urllib.parse import urlparse
from pathlib import Path
from gslib.command_runner import CommandRunner
from gslib.commands.cp import CpCommand
# from gslib.commands.rsync import RsyncCommand

import gslib

from pbpy import pbconfig
from pbpy import pbtools
from pbpy import pblog
from pbpy import pbgit
from pbpy import pbuac

# Those variable values are not likely to be changed in the future, it's safe to keep them hardcoded
uev_prefix = "ue4v:"
uplugin_ext = ".uplugin"
uproject_ext = ".uproject"
uplugin_version_key = "VersionName"
uproject_version_key = "EngineAssociation"
project_version_key = "ProjectVersion="
ddc_folder_name = "DerivedDataCache"

engine_installation_folder_regex = [r"[0-9].[0-9]{2}.*-", r"-[0-9]{8}"]

p4merge_path = ".github/p4merge/p4merge.exe"


@lru_cache()
def get_engine_version_prefix():
    return pbconfig.get('engine_prefix')


@lru_cache()
def get_editor_program():
    return "UnrealEditor" if is_ue5() else "UE4Editor"


@lru_cache()
def get_editor_relative_path():
    return f"Engine/Binaries/Win64/{get_editor_program()}.exe"


@lru_cache()
def get_editor_path():
    return get_engine_base_path() / Path(get_editor_relative_path())


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


@lru_cache()
def get_user_version():
    return pbconfig.get_user("project", "version", "latest")


def is_using_custom_version():
    return get_user_version() != "latest"


@lru_cache()
def get_latest_project_version():
    try:
        with open(pbconfig.get('defaultgame_path')) as ini_file:
            for ln in ini_file:
                if ln.startswith(project_version_key):
                    return ln.replace(project_version_key, '').rstrip()
    except Exception as e:
        pblog.exception(str(e))
        return None
    return None


@lru_cache()
def get_project_version():
    # first check if the user selected their own version
    user_version = get_user_version()
    if user_version != "latest":
        return user_version

    return get_latest_project_version()


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
        os.remove(pbconfig.get('defaultgame_path'))
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
                        fout.write(f"\t\"{uproject_version_key}\": \"{uev_prefix}{version_string}\",\n")
                    else:
                        fout.write(ln)
        os.remove(pbconfig.get('uproject_name'))
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

    # Split hotfix, update and release versions into an array
    version_split = project_version.split('.')

    if len(version_split) != 3:
        print("Incorrect project version detected")
        return False
    if increase_type == "hotfix":
        new_version = f"{version_split[0] }.{version_split[1]}.{str(int(version_split[2]) + 1)}"
    elif increase_type == "update":
        new_version = f"{version_split[0] }.{str(int(version_split[1]) + 1)}.0"
    elif increase_type == "release":
        new_version = f"{str(int(version_split[2]) + 1)}.0.0"
    else:
        return False

    print(f"Project version will be increased to {new_version}")
    return set_project_version(new_version)


@lru_cache()
def get_engine_prefix() -> str:
    return f"{pbconfig.get('engine_base_version')}-{get_engine_version_prefix()}"


@lru_cache()
def get_engine_association():
    with open(pbconfig.get('uproject_name')) as uproject_file:
        data = json.load(uproject_file)
        engine_association = str(data[uproject_version_key])
        return engine_association


@lru_cache()
def get_engine_version():
    try:
        engine_association = get_engine_association()
        if not engine_association.startswith(uev_prefix):
            # not managed by ueversionator
            return None
        build_version = engine_association.replace(f"{uev_prefix}{get_engine_prefix()}-", "")

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


@lru_cache()
def get_engine_install_root(prompt=True):
    root = pbconfig.get_user("ue4v-user", "download_dir")
    if root is None and prompt:
        curdir = Path().resolve()

        if pbconfig.get("is_ci"):
            if os.name == "nt":
                directory = (Path(curdir.anchor) / get_engine_type_folder()).resolve()
            else:
                directory = (curdir.parent / get_engine_type_folder()).resolve()
            directory.mkdir(exist_ok=True)
            return str(directory)

        print("=========================================================================")
        print("| A custom Unreal Engine build needs to be downloaded for this project. |")
        print("|   These builds can be quite large. Lots of disk space is required.    |")
        print("=========================================================================\n")
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

        # go into ue folder
        options = [(path / get_engine_type_folder()).resolve() for path in options]

        # remove duplicates
        options = list(set(options))

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
                            if directory.is_relative_to(curdir):
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
    if pbconfig.get('uses_gcs') != "True":
        return None
    output = pbtools.get_combined_output(["gsutil", "ls", bucket_url])
    bundle_name = pbconfig.get("uev_ci_bundle") if pbconfig.get("is_ci") else pbconfig.get("uev_default_bundle")
    bundle_name = pbconfig.get_user("project", "bundle", default=bundle_name)

    # e.g, "engine-4.24-PB"
    regex_prefix = f"{bundle_name}-{pbconfig.get('engine_base_version')}-{get_engine_version_prefix()}"
    versions = re.findall(regex_prefix + "-[0-9]{8}", output)
    if len(versions) == 0:
        return None
    # Find the latest version by sorting
    versions.sort()

    # Strip the build type prefix back
    result = str(versions[len(versions) - 1])
    result = result.replace(f"{bundle_name}-", '')
    return result.rstrip()


def check_ue_file_association():
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
        installation_dir = str(get_engine_base_path())
        if os.path.isdir(installation_dir):
            ue_editor_executable = os.path.join(
                installation_dir, get_editor_relative_path())
            if os.path.isfile(ue_editor_executable):
                err = pbtools.run([str(ue_editor_executable), str(Path(pbconfig.get('uproject_name')).resolve()), "-run=DerivedDataCache", "-fill"]).returncode
                if err == 0:
                    pblog.info(f"DDC generate command has exited with {err}")
                else:
                    pblog.error(f"DDC generate command has exited with {err}")
                if not check_ddc_folder_created():
                    pbtools.error_state(
                        f"DDC folder doesn't exist. Please get support from {pbconfig.get('support_channel')}")
                pblog.info("DDC data successfully generated!")
                return
        pbtools.error_state(
        f"Engine installation not found. Please get support from {pbconfig.get('support_channel')}")  
    pbtools.error_state(
    f"Error occurred while reading project version for DDC data generation. Please get support from {pbconfig.get('support_channel')}")


def clean_old_engine_installations(keep=1):
    current_version = get_engine_version_with_prefix()
    regex_pattern = engine_installation_folder_regex[0] + get_engine_version_prefix() + engine_installation_folder_regex[1]
    p = re.compile(regex_pattern)
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
    if pbconfig.get('uses_gcs') == "True":
        try:
            uev_config = configparser.ConfigParser()
            uev_config.read(".ueversionator")
            baseurl = uev_config.get("ueversionator", "baseurl", fallback=fallback)
            if baseurl:
                domain = urlparse(baseurl).hostname
                return f"gs://{domain}/"
        except Exception as e:
            pblog.exception(str(e))
    return None


@lru_cache()
def is_versionator_symbols_enabled():
    symbols = pbconfig.get_user_config().getboolean("ue4v-user", "symbols", fallback=True if pbconfig.get("is_ci") else None)
    if symbols is not None:
        return symbols

    # Symbols configuration variable is not on the file, let's add it
    response = input(f"Do you want to download debugging symbols for accurate crash logging? You can change this setting later in the {pbconfig.get('user_config')} config file. [y/N] ")
    if len(response) > 0 and response[0].lower() == "y":
        pbconfig.get_user_config()["ue4v-user"]["symbols"] = "true"
        return True
    else:
        pbconfig.get_user_config()["ue4v-user"]["symbols"] = "false"
        return False


@lru_cache()
def get_engine_type():
    return pbconfig.get('engine_type')


@lru_cache()
def is_ue5():
    return get_engine_type() == "ue5"


@lru_cache()
def get_engine_type_folder():
    return "ue" if is_ue5() else "ue4"


@lru_cache()
def get_bundle_verification_file(bundle_name):
    if bundle_name and "engine" in bundle_name:
        unreal_game = "UnrealGame" if is_ue5() else "UE4Game"
        return f"Engine/Binaries/Win64/{unreal_game}."
    else:
        return f"Engine/Binaries/Win64/{get_editor_program()}."


@lru_cache()
def get_engine_base_path():
    version = get_engine_version()
    if version is not None:
        root = get_engine_install_root()
        if root is not None:
            version = get_engine_version_with_prefix()
            return Path(root) / Path(version)
    else:
        installed_path = Path("C:\\ProgramData\\Epic\\UnrealEngineLauncher\\LauncherInstalled.dat")
        with open(str(installed_path)) as f:
            installed = json.load(f)
            for install in installed["InstallationList"]:
                if install["NamespaceId"] == "ue" and not install["AppVersion"].endswith("UserContent-Windows") and install["AppVersion"].startswith(get_engine_association()):
                    return Path(install["InstallLocation"])
    return None


@lru_cache()
def get_unreal_version_selector_path():
    if get_engine_version() is None:
        ftype_info = pbtools.get_one_line_output(["ftype", "Unreal.ProjectFile"])
        if ftype_info is not None:
            ftype_split = ftype_info.split("\"")
            if len(ftype_split) == 5:
                return Path(ftype_split[1])
        return None
    else:
        base_path = get_engine_base_path()
        return base_path / Path("Engine/Binaries/Win64/UnrealVersionSelector-Win64-Shipping.exe")


@lru_cache()
def get_uproject_path():
    return Path(pbconfig.get("uproject_name")).resolve()


def generate_project_files():
    pbtools.run([str(get_unreal_version_selector_path()), "/projectfiles", str(get_uproject_path())])
    # TODO: grab latest UnrealVersionSelector log from Saved\Logs, and print it out?


gb_multiplier = 1000 * 1000 * 1000
gb_div = 1.0 / gb_multiplier
    

def download_engine(bundle_name=None, download_symbols=False):
    is_ci = pbconfig.get("is_ci")

    root = get_engine_install_root()
    if root is not None:
        # create install dir if doesn't exist
        os.makedirs(root, exist_ok=True)

        verification_file = get_bundle_verification_file(bundle_name)
        editor_verification = get_bundle_verification_file("editor")
        engine_verification = get_bundle_verification_file("engine")
        version = get_engine_version_with_prefix()
        base_path = Path(root) / Path(version)
        symbols_path = base_path / Path(editor_verification + "pdb")
        needs_symbols = download_symbols and not symbols_path.exists()
        exe_path = base_path / Path(verification_file + "exe")
        needs_exe = not exe_path.exists()
        game_exe_path = None
        # handle downgrading to non-engine bundles
        if "engine" not in bundle_name:
            game_exe_path = base_path / Path(engine_verification + "exe")
            if game_exe_path.exists():
                needs_exe = True
                needs_symbols = download_symbols
                shutil.rmtree(str(base_path), ignore_errors=True)
        try:
            legacy_archives = pbconfig.get_user_config().getboolean("ue4v-user", "legacy", fallback=True)
        except:
            legacy_archives = True

        legacy_archives = True

        if not legacy_archives:
            pblog.success("Using new remote sync method for engine update.")

        if needs_exe or needs_symbols:
            if not is_ci and os.path.isdir(root):
                required_free_gb = 7 # extracted
                required_free_gb += 2 # archive
                
                if needs_symbols:
                    required_free_gb += 25 # extracted
                    required_free_gb += 1 # archive

                required_free_space = required_free_gb * gb_multiplier

                total, used, free = disk_usage(root)

                if free < required_free_space:
                    pblog.warning("Not enough free space. Cleaning old engine installations before download.")
                    clean_old_engine_installations()
                    total, used, free = disk_usage(root)
                    if free < required_free_space:
                        pblog.error(f"You do not have enough available space to install the engine. Please free up space on {Path(root).anchor}")
                        available_gb = free * gb_div
                        pblog.error(f"Available space: {available_gb:.2f}GB")
                        pblog.error(f"Total install size: {required_free_gb}GB")
                        must_free = required_free_gb - available_gb
                        pblog.error(f"Required space: {must_free:.2f}GB")
                        pbtools.error_state()

            if pbconfig.get('uses_gcs') == "True":
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
                    # "rs": RsyncCommand
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

    # Extract and register with ueversionator
    # TODO: handle registration
    if needs_exe:
        if False and root is not None:
            if os.name == "nt":
                try:
                    import winreg
                    engine_ver = f"{bundle_name}-{version}"
                    engine_id = f"{uev_prefix}{engine_ver}"
                    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Epic Games\Unreal Engine\Builds", access=winreg.KEY_SET_VALUE) as key:
                        # TODO: This does not work for some reason.
                        winreg.SetValueEx(key, engine_id, 0, winreg.REG_SZ, str(os.path.join(root, engine_ver)))
                except Exception as e:
                    pblog.exception(str(e))
                    return False
        else:
            command_set = ["ueversionator.exe"]

            command_set.append("-assume-valid")
            command_set.append("-user-config")
            command_set.append(pbconfig.get('user_config'))

            if bundle_name is not None:
                command_set.append("-bundle")
                command_set.append(str(bundle_name))

            if is_ue5():
                command_set.append("-ue5")
                command_set.append("-basedir")
                command_set.append("ue5")

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
                with open(pbconfig.get('user_config'), 'w') as user_config_file:
                    pbconfig.get_user_config().write(user_config_file)

            if pbtools.run(command_set).returncode != 0:
                return False

    # if not CI, run the setup tasks
    if root is not None and not is_ci and needs_exe:
        pblog.info("Installing Unreal Engine prerequisites")
        prereq_exe = "UEPrereqSetup_x64" if is_ue5() else "UE4PrereqSetup_x64"
        prereq_path = base_path / Path(f"Engine/Extras/Redist/en-us/{prereq_exe}.exe")
        pbtools.run([str(prereq_path), "/quiet"])
        pblog.info("Registering Unreal Engine file associations")
        selector_path = get_unreal_version_selector_path()
        cmdline = [selector_path, "/fileassociations"]
        if not pbuac.isUserAdmin():
            pbuac.runAsAdmin(cmdline)
        else:
            pbtools.run(cmdline)
        # generate project files for developers
        is_on_expected_branch = pbgit.compare_with_current_branch_name(pbconfig.get('expected_branch_name'))
        if not is_on_expected_branch:
            uproject = str(get_uproject_path())
            pbtools.run([selector_path, "/projectfiles", uproject])

    return True


class multi_dict(dict):
    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key].extend(value)
        else:
            super().__setitem__(key, value)
    def force_set(self, key, value):
        super().__setitem__(key, value)


class MultiConfigParser(pbconfig.CustomConfigParser):
    def _write_section(self, fp, section_name, section_items, delimiter):
        """Write a single section to the specified `fp'. Extended to write multi-value, single key."""
        fp.write("[{}]\n".format(section_name))
        for key, value in section_items:
            value = self._interpolation.before_write(self, section_name, key,
                                                     value)
            if isinstance(value, list):
                values = value
            else:
                values = [value]
            for value in values:
                if self._allow_no_value and value is None:
                    value = ""
                else:
                    value = delimiter + str(value).replace('\n', '\n\t')
                fp.write("{}{}\n".format(key, value))
        fp.write("\n")

    def _join_multiline_values(self):
        """Handles newlines being parsed as bogus values."""
        defaults = self.default_section, self._defaults
        all_sections = itertools.chain((defaults,),
                                       self._sections.items())
        for section, options in all_sections:
            for name, val in options.items():
                if isinstance(val, list):
                    # check if this is a multi value
                    length = len(val)
                    if length > 1:
                        last_entry = val[length - 1]
                        # if the last entry is empty (newline!), clear it out
                        if not last_entry:
                            del val[-1]
                    # restore it back to single value
                    if len(val) == 1:
                        val = val[0]
                val = self._interpolation.before_read(self, section, name, val)
                options.force_set(name, val)



@contextlib.contextmanager
def ue_config(path):
    config = MultiConfigParser(allow_no_value=True, delimiters=("=",), strict=False, comment_prefixes=(";",), dict_type=multi_dict, interpolation=configparser.Interpolation())
    # case sensitive
    config.optionxform = lambda option: option
    config.read(path)
    try:
        yield config
    finally:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w+') as ini_file:
            config.write(ini_file, space_around_delimiters=False)


def update_source_control():
    with ue_config("Saved/Config/Windows/SourceControlSettings.ini") as source_control_config:
        source_control_config["SourceControl.SourceControlSettings"]["Provider"] = "Git LFS 2"
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
        if username:
            git_lfs_2["LfsUserName"] = username
        else:
            pblog.warning(f"Credential retrieval failed. Please get help from {pbconfig.get('support_channel')}.")
    with ue_config("Saved/Config/Windows/EditorPerProjectUserSettings.ini") as editor_config:
        p4merge = str(Path(p4merge_path).resolve())
        editor_config["/Script/UnrealEd.EditorLoadingSavingSettings"]["TextDiffToolPath"] = f"(FilePath=\"{p4merge}\")"


# we will either error out, or succeed, so this won't matter
@lru_cache()
def is_ue_closed():
    # check if there is a UE running at all
    p = pbtools.get_running_process(get_editor_program())
    if p is None:
        # ue is not running at all
        return True
    # cheap check for our engine
    version = get_engine_version()
    if version is not None:
        root = get_engine_install_root(prompt=False)
        if root is not None:
            exe = Path(p.info["exe"])
            root = Path(root)
            if not exe.is_relative_to(root):
                # not our engine
                return True
    # finally, do an expensive open files check to ensure the project is open
    files = p.open_files()
    project_path = Path().resolve()
    found_project = False
    for file in files:
        path = Path(file.path)
        if path.is_relative_to(project_path):
            found_project = True
            break
    # if we didn't get any files, something went wrong, so take the safe route
    if len(files) < 1 or found_project:
        return False
    return True


def ensure_ue_closed():
    if not is_ue_closed():
        pbtools.error_state("Unreal Editor is currently running. Please close it before running PBSync. It may be listed only in Task Manager as a background process. As a last resort, you should log off and log in again.")


@lru_cache()
def get_base_name():
    project_path = get_uproject_path()
    return project_path.stem


@lru_cache()
def get_sln_path():
    return Path(get_base_name() + ".sln")


@lru_cache()
def get_vs_basepath():
    return pbtools.get_one_line_output(["%ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer\\vswhere.exe", "-prerelease", "-latest", "-products", "*", "-property", "installationPath"])


@lru_cache()
def get_devenv_path():
    vs_basepath = get_vs_basepath()
    if vs_basepath:
        return Path(vs_basepath, "Common7", "IDE", "devenv.exe")
    return None


def build_source():
    base = get_engine_base_path()
    get_ms_build = base / "Engine" / "Build" / "BatchFiles" / "GetMSBuildPath.bat"
    pbtools.run_with_output([str(get_ms_build)], env_out=["MSBUILD_EXE"])
    ms_build = os.environ.get("MSBUILD_EXE")
    if ms_build is None:
        pbtools.error_state("Could not find MSBuild.")
    sln_path = get_sln_path().resolve()
    proc = pbtools.run_stream([ms_build, str(sln_path), "/nologo", "/t:build", '/property:configuration=Development Editor', "/property:Platform=Win64"])
    if proc.returncode:
        pbtools.error_state("Build failed.")


def build_game(configuration="Shipping"):
    base = get_engine_base_path()
    uat_path = base / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat"
    proc = pbtools.run_stream([uat_path, "BuildCookRun", f"-project={str(get_uproject_path())}", f"-clientconfig={configuration}", "-NoP4", "-NoCodeSign", "-cook", "-build", "-stage", "-prereqs", "-pak", "-CrashReporter"])
    if proc.returncode:
        pbtools.error_state("Build failed.")

platform_names = {"Windows": "Win64", "Darwin": "Mac", "Linux": "Linux"}


@lru_cache()
def get_platform_name():
    return platform_names[platform.system()]

binaries_paths = ["Binaries", "Plugins/**/Binaries"]


def package_binaries():
    binaries_zip = Path("Binaries.zip")
    binaries_zip.unlink(missing_ok=True)
    base_path = Path(".")

    for binaries_path in binaries_paths:
        for ilk in base_path.glob(f"{binaries_path}/Win64/*.ilk"):
            ilk.unlink()

    if pbconfig.get("package_pdbs") != "True":
        for binaries_path in binaries_paths:
            for pdb in base_path.glob(f"{binaries_path}/Win64/*.pdb"):
                pdb.unlink()
    
    hashes = dict()
    with zipfile.ZipFile("Binaries.zip", "a") as zipf:
        for binaries_path in binaries_paths:
            for file in base_path.glob(f"{binaries_path}/**/*"):
                if not file.is_file():
                    continue
                filename = str(file)
                zipf.write(filename, filename)
                hashes[filename] = pbtools.get_hash(filename)

    hashes["Binaries.zip"] = pbtools.get_hash("Binaries.zip")

    pbtools.make_json_from_dict(hashes, pbconfig.get("checksum_file"))


def inspect_source(all=False):
    if all:
        modified_files_list = "Source\**\*"
    else:
        modified_paths = pbgit.get_modified_files()
        if len(modified_paths) < 1:
            pblog.info("No modified files to inspect, done. Use --build inspectall if you'd like to inspect the entire project.")
            return
        modified_files = [str(path) for path in modified_paths if str(path).startswith("Source")]
        modified_files_list = ";".join(modified_files)
    version = pbconfig.get("resharper_version")
    saved_dir = Path("Saved")
    zip_name = f"JetBrains.ReSharper.CommandLineTools.{version}.zip"
    zip_path = saved_dir / Path(zip_name)
    if not zip_path.exists():
        pblog.info(f"Downloading Resharper {version}")
        url = f"https://download-cdn.jetbrains.com/resharper/dotUltimate.{version}/{zip_name}"
        with urllib.request.urlopen(url) as response, open(str(zip_path), 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    resharper_dir = saved_dir / Path("ResharperCLI")
    pblog.info(f"Unpacking Resharper {version}")
    shutil.unpack_archive(str(zip_path), str(resharper_dir))
    resharper_exe = resharper_dir / Path("inspectcode.exe")
    inspect_file = "Saved\InspectionResults.txt"
    pblog.info(f"Running Resharper {version}")
    proc = pbtools.run_stream([
        str(resharper_exe),
        str(get_sln_path()),
        "--no-swea",
        "--properties:Platform=Win64;Configuration=Development Editor",
        f"--include={modified_files_list}",
        f"--project={get_base_name()}",
        "-f=Text",  # TODO: maybe switch to XML for more robust parsing?
        f"-o={inspect_file}"
    ])
    if proc.returncode:
        pbtools.error_state("Resharper inspectcode failed.")
    has_error = False
    # TODO: make this configurable
    non_errors = [
        "Possibly unused #include directive",
        " is hidden in derived class ",
        " hides a non-virtual function from class ",
        "Possibly unintended object slicing",
        "Cannot resolve symbol",
        " can be made const",
        " does not have a 'virtual' specifier",
        "style cast is used instead of",
        "Member function can be made static",
        "can be moved to inner scope",
        "Unreachable code",
    ]
    # it is UTF-8 BOM
    with open(inspect_file, encoding='utf-8-sig') as f:
        lines = f.readlines()
        for line in lines:
            # if blank, skip
            line_strip = line.strip()
            if not line_strip:
                continue
            if line_strip.startswith("Solution ") or line_strip.startswith("Project "):
                pblog.info(line)
            elif pbtools.it_has_any(line, *non_errors):
                pblog.warning(line)
            else:
                pblog.error(line)
                has_error = True
    if has_error:
        pbtools.error_state("Resharper inspectcode found errors.")
    os.remove(inspect_file)
    shutil.rmtree(str(resharper_dir))
