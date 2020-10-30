import subprocess
import re
from shutil import move
from shutil import rmtree
from shutil import disk_usage
from os import remove
from functools import lru_cache
from urllib.parse import urlparse
from gslib.command_runner import CommandRunner
from gslib.commands.cp import CpCommand
from gslib.commands.rsync import RsyncCommand
import os
import json
import glob
import pathlib
import gslib

from pbpy import pbconfig
from pbpy import pbtools
from pbpy import pblog

# Those variable values are not likely to be changed in the future, it's safe to keep them hardcoded
uplugin_ext = ".uplugin"
uproject_ext = ".uproject"
uplugin_version_key = "VersionName"
uproject_version_key = "EngineAssociation"
project_version_key = "ProjectVersion="
ddc_folder_name = "DerivedDataCache"
ue4_editor_relative_path = "Engine/Binaries/Win64/UE4Editor.exe"
engine_installation_folder_regex = "[0-9].[0-9]{2}-PB-[0-9]{8}"
engine_version_prefix = "PB"


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


def get_project_version():
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
                        fout.write(f"\t\"EngineAssociation\": \"ue4v:{version_string}\",\n")
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
def get_engine_prefix():
    return f"{pbconfig.get('engine_base_version')}-{engine_version_prefix}"


@lru_cache()
def get_engine_version():
    try:
        with open(pbconfig.get('uproject_name')) as uproject_file:
            data = json.load(uproject_file)
            engine_association = data[uproject_version_key]
            build_version = engine_association[-8:]

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
    return pbconfig.get_user("ue4v-user", "download_dir")


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
                err = subprocess.run([str(ue_editor_executable), os.path.join(
                    os.getcwd(), pbconfig.get('uproject_name')), "-run=DerivedDataCache", "-fill"], shell=True).returncode
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
    "Error occurred while trying to read project version for DDC data generation. Please get support from #tech-support")


def clean_old_engine_installations():
    current_version = get_engine_version_with_prefix()
    p = re.compile(engine_installation_folder_regex)
    if current_version is not None:
        engine_install_root = get_engine_install_root()
        if engine_install_root is not None and os.path.isdir(engine_install_root):
            folders = os.listdir(engine_install_root)
            for folder in folders:
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
def get_versionator_gsuri():
    try:
        with open('.ue4versionator') as config_file:
            for ln in config_file:
                if "baseurl" in ln:
                    ln = ln.rstrip()
                    config_map = ln.split(" = ")
                    if len(config_map) == 2:
                        baseurl = config_map[1]
                        domain = urlparse(baseurl).hostname
                        return f"gs://{domain}/"
    except Exception as e:
        pblog.exception(str(e))
    return None


@lru_cache()
def is_versionator_symbols_enabled():
    symbols = pbconfig.get_user_config().getboolean("ue4v-user", "symbols")
    if symbols is not None:
        return symbols

    if pbconfig.get("is_ci"):
        return False

    # Symbols configuration variable is not on the file, let's add it
    response = input("Do you want to download debugging symbols for accurate crash logging? You can change this setting later in the .ue4v-user config file. [y/N]")
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


def run_ue4versionator(bundle_name=None, download_symbols=False):
    required_free_gb = 7
    
    if download_symbols:
        required_free_gb += 23

    required_free_space = required_free_gb * 1000 * 1000 * 1000

    root = get_engine_install_root()
    # TODO: prompt for root
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
            legacy_archives = pbconfig.get_user_config().getboolean("ue4v-user", "legacy", fallback=False) or int(get_engine_version()) <= 20201028
        except:
            legacy_archives = True

        legacy_archives = False

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
            patterns = [pattern + f"-{version}.7z" if legacy_archives else "/" for pattern in patterns]
            gcs_bucket = get_versionator_gsuri()
            for pattern in patterns:
                gcs_uri = f"{gcs_bucket}{pattern}"
                dst = f"file://{root}"
                command_runner.RunNamedCommand('cp' if legacy_archives else 'rs', args=["-n", gcs_uri, dst], collect_analytics=False, parallel_operations=True)

    # Extract and register with ue4versionator
    # TODO: handle registration
    command_set = ["ue4versionator.exe"]

    command_set.append("-assume-valid")

    if bundle_name is not None:
        command_set.append("-bundle")
        command_set.append(str(bundle_name))

    if pbconfig.get("is_ci"):
        # If we're CI, use another config file
        command_set.append("-user-config")
        command_set.append(pbconfig.get_user_config_filename())

    return subprocess.run(command_set, shell=True).returncode
