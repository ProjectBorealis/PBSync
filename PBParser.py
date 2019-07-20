import json
import glob
import subprocess
import re
from shutil import move
from os import remove
from os import path

uproject_path = "ProjectBorealis.uproject"
uproject_version_key = "EngineAssociation"

defaultgame_path = "Config/DefaultGame.ini"
defaultgame_version_key = "ProjectVersion="

uplugin_version_key = "VersionName"

versionator_config_path = ".ue4v-user"

uplugin_ext = ".uplugin"

def IsVersionatorSymbolsEnabled():
    if not path.isfile(versionator_config_path):
        # Config file somehow haven't generated yet, return False
        return False

    with open(versionator_config_path, "r") as config_file:
        for ln in config_file:
            if "Symbols" in ln:
                if "False" in ln or "false" in ln:
                    return False
                elif "True" in ln or "true" in ln:
                    return True

    # Symbols configuration variable is not on the file, let's add it
    with open(versionator_config_path, "a+") as config_file:   
        response = input("Do you want to also download debugging symbols for accurate crash logging? [y/n]")
        if response == "y" or response == "Y":
            config_file.write("Symbols = True")
            return True
        else:
            config_file.write("Symbols = False")
            return False


def GetPluginVersion(plugin_name):
    plugin_root = "Plugins/" + plugin_name
    for uplugin_path in glob.glob(plugin_root + "/*" + uplugin_ext):
        with open(uplugin_path, "r") as uplugin_file:  
            data = json.load(uplugin_file)
            version = data[uplugin_version_key]
            # Some plugins have strange versions with only major and minor versions, add patch version for compatibility with nuget
            if version.count('.') == 1:
                version = version + ".0"
            return version
    return "0.0.0"

def GetProjectVersion():
    with open(defaultgame_path, "r") as ini_file:
        for ln in ini_file:
            if ln.startswith(defaultgame_version_key):
                return ln.replace(defaultgame_version_key, '').rstrip()
    return "0.0.0"

def SetEngineVersion(version_string):
    temp_path = "tmp.txt"
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
    return True

def GetSuffix():
    try:
        with open(uproject_path, "r") as uproject_file:  
            data = json.load(uproject_file)
            engine_association = data[uproject_version_key]
            build_version = "b" + engine_association[-8:]
            # We're using local build version in .uproject file
            if "}" in build_version:
                return ""
            return "b" + engine_association[-8:]
    except:
        return ""
    return ""

def GetLatestAvailableEngineVersion(bucket_url):
    output = subprocess.getoutput(["gsutil", "ls", bucket_url])
    versions = re.findall("[4].[0-9]{2}-PB-[0-9]{8}", str(output))
    if len(versions) == 0:
        return None
    versions.sort()
    return str(versions[len(versions) - 1])
    