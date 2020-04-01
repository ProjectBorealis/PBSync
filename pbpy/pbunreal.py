import subprocess
import re
from shutil import move
from shutil import rmtree
from os import remove
import os
import json

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
    return pbconfig.get('engine_base_version') + "-" + engine_version_prefix

def get_engine_date_suffix():
    try:
        with open(pbconfig.get('uproject_name'), "r") as uproject_file:  
            data = json.load(uproject_file)
            engine_association = data[uproject_version_key]
            build_version = "b" + engine_association[-8:]
            # We're using local build version in .uproject file
            if "}" in build_version:
                return None
            return "b" + engine_association[-8:]
    except Exception as e:
        pblog.exception(str(e))
        return None
    return None

def get_plugin_version(plugin_name):
    plugin_root = "Plugins/" + plugin_name
    for uplugin_path in glob.glob(plugin_root + "/*" + uplugin_ext):
        with open(uplugin_path, "r") as uplugin_file:  
            data = json.load(uplugin_file)
            version = data[uplugin_version_key]
            # Some plugins have strange versions with only major and minor versions, add patch version for compatibility with nuget
            if version.count('.') == 1:
                version = version + ".0"
            return version
    return None

def get_project_version():
    try:
        with open(pbconfig.get('defaultgame_path'), "r") as ini_file:
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
        with open(pbconfig.get('defaultgame_path'), "r") as ini_file:
            with open(temp_path, "wt") as fout:
                for ln in ini_file:
                    if project_version_key in ln:
                        fout.write(	"ProjectVersion=" + version_string + "\n")
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
        with open(pbconfig.get('uproject_name'), "r") as uproject_file:
            with open(temp_path, "wt") as fout:
                for ln in uproject_file:
                    if uproject_version_key in ln:
                        fout.write(	"\t\"EngineAssociation\": \"ue4v:" + version_string + "\",\n")
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
    new_version = ""
    if project_version is None:
        return False

    # Split hotfix, stable and release versions into an array
    version_split = project_version.split('.')

    if len(version_split) != 3:
        print("Incorrect project version detected")
        return False
    if increase_type == "hotfix":
        new_version = version_split[0] + "." + version_split[1] + "." + str(int(version_split[2]) + 1)
    elif increase_type == "stable":
        new_version = version_split[0] + "." + str(int(version_split[1]) + 1) + ".0"
    elif increase_type == "public":
        new_version = str(int(version_split[2]) + 1) + ".0.0"
    else:
        return False
    
    print("Project version will be increased to " + new_version)
    return set_project_version(new_version)

def get_engine_version():
    try:
        with open(pbconfig.get('uproject_name'), "r") as uproject_file:  
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
    return None

def get_engine_version_with_prefix():
    engine_ver_number = get_engine_version()
    if engine_ver_number != None:
        return get_engine_prefix() + "-" + engine_ver_number
    return None

def get_engine_install_root():
    try:
        with open(pbconfig.get('versionator_config_path'), "r") as config_file:
            for ln in config_file:
                if "download_dir" in ln:
                    split_str = ln.split("=")
                    if len(split_str) == 2:
                        return split_str[1].strip()
    except Exception as e:
        pblog.exception(str(e))
        return None

def get_latest_available_engine_version(bucket_url):
    output = subprocess.getoutput(["gsutil", "ls", bucket_url])
    versions = re.findall("[4].[0-9]{2}-PB-[0-9]{8}", str(output))
    if len(versions) == 0:
        return None
    # Find the latest version by sorting
    versions.sort()
    return str(versions[len(versions) - 1])

def check_ue4_file_association():
    file_assoc_result = subprocess.getoutput(["assoc", uproject_ext])
    return "Unreal.ProjectFile" in file_assoc_result

def check_ddc_folder_created():
    ddc_path = os.path.join(os.getcwd(), ddc_folder_name)
    return os.path.isdir(ddc_path)

def generate_ddc_data():
    pblog.info("Generating DDC data, please wait... (This may take up to one hour only for the initial run)")
    current_version = get_engine_version_with_prefix()
    if current_version != None:
        engine_install_root = get_engine_install_root()
        installation_dir = os.path.join(engine_install_root, current_version)
        if os.path.isdir(installation_dir):
            ue_editor_executable = os.path.join(installation_dir, ue4_editor_relative_path)
            if os.path.isfile(ue_editor_executable):
                err = subprocess.call([str(ue_editor_executable), os.path.join(os.getcwd(), pbconfig.get('uproject_name')), "-run=DerivedDataCache", "-fill"])
                pblog.info("DDC generate command has exited with " + str(err))
                if not check_ddc_folder_created():
                    pbtools.error_state("DDC folder doesn't exist. Please get support from #tech-support")
                    return
                pblog.info("DDC data successfully generated!")
                return
    pbtools.error_state("Error occured while trying to read project version for DDC data generation. Please get support from #tech-support")

def clean_old_engine_installations():
    current_version = get_engine_version_with_prefix()
    p = re.compile(engine_installation_folder_regex)
    if current_version != None:
        engine_install_root = get_engine_install_root()
        if engine_install_root != None and os.path.isdir(engine_install_root):
            dirs = os.listdir(engine_install_root)
            for dir in dirs:
                # Do not remove folders if they do not match with installation folder name pattern
                # Also do not remove files. Only remove folders
                full_path = os.path.join(engine_install_root, dir)
                if dir != current_version and p.match(dir) != None and os.path.isdir(full_path):
                    print("Removing old engine installation: " + str(full_path) + "...")
                    try:
                        shutil.rmtree(full_path)
                        print("Removal was successful!")
                    except Exception as e:
                        pblog.exception(str(e))
                        print("Something went wrong while removing engine folder " + str(full_path) + " Please try removing it manually.")
            return True

    return False