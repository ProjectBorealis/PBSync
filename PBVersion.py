import json
import glob
import subprocess

uproject_path = "ProjectBorealis.uproject"
uproject_version_key = "EngineAssociation"

defaultgame_path = "Config/DefaultGame.ini"
defaultgame_version_key = "ProjectVersion="

uplugin_version_key = "VersionName"

uplugin_ext = ".uplugin"

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