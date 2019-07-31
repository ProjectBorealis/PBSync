import subprocess
import re
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
############################################################################

def is_versionator_symbols_enabled():
    if not path.isfile(versionator_config_path):
        # Config file somehow isn't generated yet, only get a response, but do not write anything into config
        response = input("Do you want to also download debugging symbols for accurate crash logging? You can change that choice later in .ue4v-user config file [y/n]")
        if response == "y" or response == "Y":
            return True
        else:
            return False

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

    # Symbols configuration variable is not on the file, let's add it
    with open(versionator_config_path, "a+") as config_file:   
        response = input("Do you want to also download debugging symbols for accurate crash logging? You can change that choice later in .ue4v-user config file [y/n]")
        if response == "y" or response == "Y":
            config_file.write("\nSymbols = True")
            return True
        else:
            config_file.write("\nSymbols = False")
            return False

def get_project_version():
    with open(defaultgame_path, "r") as ini_file:
        for ln in ini_file:
            if ln.startswith(defaultgame_version_key):
                return ln.replace(defaultgame_version_key, '').rstrip()
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

def get_latest_available_engine_version(bucket_url):
    output = subprocess.getoutput(["gsutil", "ls", bucket_url])
    versions = re.findall("[4].[0-9]{2}-PB-[0-9]{8}", str(output))
    if len(versions) == 0:
        return None
        
    # Find the latest version by sorting
    versions.sort()
    return str(versions[len(versions) - 1])
    