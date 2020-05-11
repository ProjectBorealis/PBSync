import subprocess
import re
from shutil import move
from shutil import rmtree
from os import remove
import os
import json
import glob

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


def get_engine_prefix():
    return f"{pbconfig.get('engine_base_version')}-{engine_version_prefix}"


def get_engine_date_suffix():
    try:
        with open(pbconfig.get('uproject_name')) as uproject_file:
            data = json.load(uproject_file)
            engine_association = data[uproject_version_key]
            build_version = f"b{engine_association[-8:]}"
            # We're using local build version in .uproject file
            if "}" in build_version:
                return None
            return f"b{engine_association[-8:]}"
    except Exception as e:
        pblog.exception(str(e))
        return None


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
        pblog.error("Incorrect project version detected")
        return False
    if increase_type == "hotfix":
        new_version = f"{version_split[0] }.{version_split[1]}.{str(int(version_split[2]) + 1)}"
    elif increase_type == "stable":
        new_version = f"{version_split[0] }.{str(int(version_split[1]) + 1)}.0"
    elif increase_type == "public":
        new_version = f"{str(int(version_split[2]) + 1)}.0.0"
    else:
        return False

    pblog.info(f"Project version will be increased to {new_version}")
    return set_project_version(new_version)


def get_engine_version(only_date=True):
    try:
        with open(pbconfig.get('uproject_name')) as uproject_file:
            data = json.load(uproject_file)
            engine_association = data[uproject_version_key]
            build_version = engine_association[-8:]

            if "}" in build_version:
                # Means we're using local build version in .uproject file
                return None

            if not only_date:
                build_version = f"{pbconfig.get('engine_base_version')}-{engine_version_prefix}-{build_version}"

            return build_version
    except Exception as e:
        pblog.exception(str(e))
        return None


def get_engine_version_with_prefix():
    engine_ver_number = get_engine_version()
    if engine_ver_number is not None:
        return f"{get_engine_prefix()}-{engine_ver_number}"
    return None


def get_engine_install_root():
    try:
        with open(pbconfig.get('ue4v_user_config')) as config_file:
            for ln in config_file:
                if "download_dir" in ln:
                    split_str = ln.split("=")
                    if len(split_str) == 2:
                        return split_str[1].strip()
    except Exception as e:
        pblog.exception(str(e))
        return None


def get_latest_available_engine_version(bucket_url):
    output = pbtools.get_combined_output(["gsutil", "ls", bucket_url])
    pblog.info(output)
    build_type = pbconfig.get("ue4v_default_bundle")
    if pbconfig.get("is_ci"):
        # We should get latest version of ciengine instead
        build_type = pbconfig.get("ue4v_ci_bundle")

    # e.g, "engine-4.24-PB"
    regex_prefix = f"{build_type}-{pbconfig.get('engine_base_version')}-{engine_version_prefix}"
    versions = re.findall(regex_prefix + "-[0-9]{8}", output)
    print(versions)
    if len(versions) == 0:
        return None
    # Find the latest version by sorting
    versions.sort()

    # Strip the build type prefix back
    result = str(versions[len(versions) - 1])
    result = result.replace(f"{build_type}-", '')
    return result


def check_ue4_file_association():
    file_assoc_result = pbtools.get_combined_output(["assoc", uproject_ext])
    return "Unreal.ProjectFile" in file_assoc_result


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
                    return
                pblog.info("DDC data successfully generated!")
                return
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
                    pblog.info(f"Removing old engine installation: {str(full_path)}...")
                    try:
                        rmtree(full_path)
                        pblog.info("Removal was successful!")
                    except Exception as e:
                        pblog.exception(str(e))
                        pblog.error(f"Something went wrong while removing engine folder {str(full_path)}. Please try removing it manually.")
            return True

    return False


def is_versionator_symbols_enabled():
    if not os.path.isfile(pbconfig.get('ue4v_user_config')):
        # Config file somehow isn't generated yet, only get a response, but do not write anything into config
        response = input(
            "Do you want to download debugging symbols for accurate crash logging? You can change this setting later in the .ue4v-user config file. [y/n]")
        if response == "y" or response == "Y":
            return True
        else:
            return False

    try:
        with open(pbconfig.get('ue4v_user_config')) as config_file:
            for ln in config_file:
                if "Symbols" in ln or "symbols" in ln:
                    if "False" in ln or "false" in ln:
                        return False
                    elif "True" in ln or "true" in ln:
                        return True
                    else:
                        # Incorrect config
                        return False
    except Exception as e:
        pblog.exception(str(e))
        return False

    # Symbols configuration variable is not on the file, let's add it
    try:
        with open(pbconfig.get('ue4v_user_config'), "a+") as config_file:
            response = input(
                "Do you want to download debugging symbols for accurate crash logging? You can change this setting later in the .ue4v-user config file. [y/n]")
            if response == "y" or response == "Y":
                config_file.write("\nsymbols = true")
                return True
            else:
                config_file.write("\nsymbols = false")
                return False
    except Exception as e:
        pblog.exception(str(e))
        return False


def run_ue4versionator(bundle_name=None, download_symbols=False):
    command_set = ["ue4versionator.exe"]

    if not (bundle_name is None):
        command_set.append("--bundle")
        command_set.append(str(bundle_name))

    if download_symbols:
        command_set.append("--with-symbols")

    if pbconfig.get("is_ci"):
        # If we're CI, use another config file
        command_set.append("-user-config")
        command_set.append(pbconfig.get("ue4v_ci_config"))

    return subprocess.run(command_set, shell=True).returncode
