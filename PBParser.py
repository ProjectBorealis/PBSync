import subprocess
import re
import time
from shutil import move
from os import remove
from os import path
import json

### Globals
uproject_path = "ProjectBorealis.uproject"
uproject_version_key = "EngineAssociation"

defaultgame_path = "Config/DefaultGame.ini"
defaultgame_version_key = "ProjectVersion="

versionator_config_path = ".ue4v-user"

ddc_version_path = "DerivedDataCache/.ddc_version"
ddc_version = 1

engine_version_prefix = "4.23-PB-"
############################################################################

def get_git_version():
    installed_version = subprocess.getoutput(["git", "--version"])
    installed_version_parsed = re.findall("[0-9].[0-9]{2}.[0-9]", str(installed_version))
    if len(installed_version_parsed) == 0 or len(installed_version_parsed[0]) == 0:
        return ""

    return installed_version_parsed[0]

def get_lfs_version():
    installed_version = subprocess.getoutput(["git-lfs", "--version"])
    installed_version_parsed = re.findall("[0-9].[0-9].[0-9]", str(installed_version))
    if len(installed_version_parsed) == 0 or len(installed_version_parsed[0]) == 0:
        return ""

    # Index 0 is lfs version, other matched version is Go compiler version
    return installed_version_parsed[0]

# -2: Parse error
# -1: Old version
# 0: Expected version
# 1: Newer version
def compare_git_version(compared_version):
    installed_version = str(get_git_version()).split(".")
    if len(installed_version) != 3:
        return -2

    expected_version = str(compared_version).split(".")
    if len(expected_version) != 3:
        return -2
    
    if (int(installed_version[0]) == int(expected_version[0])) and (int(installed_version[1]) == int(expected_version[1])) and (int(installed_version[2]) == int(expected_version[2])):
        # Same version
        return 0
    
    # Not same version:
    if int(installed_version[0]) < int(expected_version[0]):
        return -1
    elif int(installed_version[1]) < int(expected_version[1]):
        return -1
    elif int(installed_version[2]) < int(expected_version[2]):
        return -1
    
    # Not older version:
    if int(installed_version[0]) > int(expected_version[0]):
        return 1
    elif int(installed_version[1]) > int(expected_version[1]):
        return 1
    elif int(installed_version[2]) > int(expected_version[2]):
        return 1

    # Something went wrong, return parse error
    return -2

# -2: Parse error
# -1: Old version
# 0: Expected version
# 1: Newer version
def compare_lfs_version(compared_version):
    installed_version = str(get_lfs_version()).split(".")
    if len(installed_version) != 3:
        return -2
    
    expected_version = str(compared_version).split(".")
    if len(installed_version) != 3:
        return -2
    
    if (int(installed_version[0]) == int(expected_version[0])) and (int(installed_version[1]) == int(expected_version[1])) and (int(installed_version[2]) == int(expected_version[2])):
        # Same version
        return 0
    
    # Not same version:
    if int(installed_version[0]) < int(expected_version[0]):
        return -1
    elif int(installed_version[1]) < int(expected_version[1]):
        return -1
    elif int(installed_version[2]) < int(expected_version[2]):
        return -1
    
    # Not older version:
    if int(installed_version[0]) > int(expected_version[0]):
        return 1
    elif int(installed_version[1]) > int(expected_version[1]):
        return 1
    elif int(installed_version[2]) > int(expected_version[2]):
        return 1

    # Something went wrong, return parse error
    return -2

def is_versionator_symbols_enabled():
    if not path.isfile(versionator_config_path):
        # Config file somehow isn't generated yet, only get a response, but do not write anything into config
        response = input("Do you want to also download debugging symbols for accurate crash logging? You can change that choice later in .ue4v-user config file [y/n]")
        if response == "y" or response == "Y":
            return True
        else:
            return False

    try:
        with open(versionator_config_path, "r") as config_file:
            for ln in config_file:
                if "Symbols" in ln:
                    if "False" in ln or "false" in ln:
                        return False
                    elif "True" in ln or "true" in ln:
                        return True
                    else:
                        # Incorrect config
                        return False
    except:
        return False

    # Symbols configuration variable is not on the file, let's add it
    try:
        with open(versionator_config_path, "a+") as config_file:   
            response = input("Do you want to also download debugging symbols for accurate crash logging? You can change that choice later in .ue4v-user config file [y/n]")
            if response == "y" or response == "Y":
                config_file.write("\nSymbols = True")
                return True
            else:
                config_file.write("\nSymbols = False")
                return False
    except:
        return False

def get_project_version():
    try:
        with open(defaultgame_path, "r") as ini_file:
            for ln in ini_file:
                if ln.startswith(defaultgame_version_key):
                    return ln.replace(defaultgame_version_key, '').rstrip()
    except:
        return None
    return None

def set_project_version(version_string):
    temp_path = "tmpProj.txt"
    # Create a temp file, do the changes there, and replace it with actual file
    try:
        with open(defaultgame_path, "r") as ini_file:
            with open(temp_path, "wt") as fout:
                for ln in ini_file:
                    if defaultgame_version_key in ln:
                        fout.write(	"ProjectVersion=" + version_string + "\n")
                    else:
                        fout.write(ln)
        remove(defaultgame_path)
        move(temp_path, defaultgame_path)
    except:
        return False
    return True

def set_engine_version(version_string):
    temp_path = "tmpEng.txt"
    try:
        # Create a temp file, do the changes there, and replace it with actual file
        with open(uproject_path, "r") as uproject_file:
            with open(temp_path, "wt") as fout:
                for ln in uproject_file:
                    if uproject_version_key in ln:
                        fout.write(	"\t\"EngineAssociation\": \"ue4v:" + version_string + "\",\n")
                    else:
                        fout.write(ln)
        remove(uproject_path)
        move(temp_path, uproject_path)
    except:
        return False
    return True

def project_version_increase(increase_type):
    project_version = get_project_version()
    new_version = ""
    if project_version is None:
        return False

    # Split release, major and minor versions into an array
    version_split = project_version.split('.')

    if len(version_split) != 3:
        print("Incorrect project version detected")
        return False

    if increase_type == "minor":
        new_version = version_split[0] + "." + version_split[1] + "." + str(int(version_split[2]) + 1)
    
    elif increase_type == "major":
        new_version = version_split[0] + "." + str(int(version_split[1]) + 1) + ".0"

    elif increase_type == "release":
        new_version = str(int(version_split[2]) + 1) + ".0.0"

    else:
        return False
    
    print("Project version will be increased to " + new_version)
    return set_project_version(new_version)

def get_engine_version():
    try:
        with open(uproject_path, "r") as uproject_file:  
            data = json.load(uproject_file)
            engine_association = data[uproject_version_key]
            build_version = engine_association[-8:]
            
            if "}" in build_version:
                # Means we're using local build version in .uproject file
                return None
            return build_version
    except:
        return None
    return None

def get_engine_version_with_prefix():
    engine_ver_number = get_engine_version()
    if engine_ver_number != None:
        return engine_version_prefix + engine_ver_number

    return None

def get_engine_install_root():
    try:
        with open(versionator_config_path, "r") as config_file:
            for ln in config_file:
                if "download_dir" in ln:
                    split_str = ln.split("=")
                    if len(split_str) == 2:
                        return split_str[1].strip()
    except:
        return None

def get_latest_available_engine_version(bucket_url):
    output = subprocess.getoutput(["gsutil", "ls", bucket_url])
    versions = re.findall("[4].[0-9]{2}-PB-[0-9]{8}", str(output))
    if len(versions) == 0:
        return None
        
    # Find the latest version by sorting
    versions.sort()
    return str(versions[len(versions) - 1])

def ddc_needs_regeneration():
    if path.isfile(ddc_version_path):
        try:
            with open(ddc_version_path, 'r') as ddc_version_file:
                current_version = ddc_version_file.readline(1)
                if int(current_version) < ddc_version:
                    return True
                else:
                    return False
        except:
            return True
    else:
        # DDC is not runned yet on this system, or it's removed
        return True
        
def ddc_update_version():
    try:
        with open(ddc_version_path, 'w') as ddc_version_file:
            ddc_version_file.write(str(ddc_version))
            return True
    except:
        return False