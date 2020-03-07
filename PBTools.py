import os
import os.path
import psutil
import subprocess
import shutil
import time
import re

# PBSync Imports
import PBParser
import PBConfig

engine_installation_folder_regex = "[0-9].[0-9]{2}-PB-[0-9]{8}"

def push_build(branch_type):
    # Wrap executable with DRM
    result = subprocess.call([PBConfig.get('dispatch_executable'), "build", "drm-wrap", str(os.environ['DISPATCH_APP_ID']), PBConfig.get('dispatch_drm')])
    if result != 0:
        return False

    branch_id = "-1"
    if branch_type == "stable":
        branch_id = str(os.environ['DISPATCH_ALPHA_BID'])
    elif branch_type == "public":
        branch_id = str(os.environ['DISPATCH_BETA_BID'])
    else:
        return False

    # Push & Publish the build
    result = subprocess.call([PBConfig.get('dispatch_executable'), "build", "push", branch_id, PBConfig.get('dispatch_config'), PBConfig.get('dispatch_stagedir'), "-p"])
    return result == 0

def check_remote_connection():
    current_url = subprocess.check_output(["git", "remote", "get-url", "origin"])
    # recent_url = PBConfig.get("git_url")

    # if current_url != recent_url:
    #     subprocess.call(["git", "remote", "set-url", "origin", recent_url])

    # current_url = subprocess.check_output(["git", "remote", "get-url", "origin"])
    out = subprocess.check_output(["git", "ls-remote", "--exit-code", "-h"])
    return not ("fatal" in str(out)), str(current_url)

def check_ue4_file_association():
    file_assoc_result = subprocess.getoutput(["assoc", ".uproject"])
    return "Unreal.ProjectFile" in file_assoc_result

def pbget_pull():
    os.chdir("PBGet")
    subprocess.call(["PBGet.exe", "resetcache"])
    status = subprocess.call(["PBGet.exe", "pull", "--threading", "false"])
    os.chdir("..")
    return status

def pbget_push(apikey):
    os.chdir("PBGet")
    status = subprocess.call(["PBGet.exe", "push", "--source", PBConfig.get('pbget_url'), "--apikey", apikey])
    os.chdir("..")
    return status

def check_running_process(process_name):
    try:
        if process_name in (p.name() for p in psutil.process_iter()):
            return True
    except:
        pass
    return False

def run_ue4versionator():
    if PBParser.is_versionator_symbols_enabled():
        return subprocess.call(["ue4versionator.exe", "--with-symbols"])
    else:
        return subprocess.call(["ue4versionator.exe"])

def clean_old_engine_installations():
    current_version = PBParser.get_engine_version_with_prefix()
    global engine_installation_folder_regex
    p = re.compile(engine_installation_folder_regex)
    if current_version != None:
        engine_install_root = PBParser.get_engine_install_root()
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
                    except:
                        print("Something went wrong while removing engine folder " + str(full_path) + " Please try removing it manually.")
            return True

    return False

# 0: DDC generation was successful
# 1: DDC data generation was not successful because of IO errors
# 2: Generated DDC data is smaller than expected
def generate_ddc_data():
    current_version = PBParser.get_engine_version_with_prefix()
    
    if current_version != None:
        engine_install_root = PBParser.get_engine_install_root()
        installation_dir = os.path.join(engine_install_root, current_version)
        if os.path.isdir(installation_dir):
            ue_editor_executable = os.path.join(installation_dir, "Engine/Binaries/Win64/UE4Editor.exe")
            if os.path.isfile(ue_editor_executable):
                err = subprocess.call([str(ue_editor_executable), os.path.join(os.getcwd(), PBConfig.get('uproject_path')), "-run=DerivedDataCache", "-fill"])
                if not check_ddc_data():
                    return 2, err
                return 0, err
    
    return 1, err

def get_size(start_path):
    total_size = -1
    try:
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except:
        return -1
    return total_size

def check_ddc_data():
    ddc_path = os.path.join(os.getcwd(), "DerivedDataCache")
    return (get_size(ddc_path) > PBConfig.get('ddc_expected_min_size'))