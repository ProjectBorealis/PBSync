import os
import os.path
import psutil
import subprocess
import shutil
import time

# PBSync Imports
import PBParser
import PBConfig

def check_remote_connection():
    current_url = subprocess.check_output(["git", "remote", "get-url", "origin"])
    recent_url = PBConfig.get("git_url")

    if current_url != recent_url:
        subprocess.call(["git", "remote", "set-url", "origin", recent_url])

    current_url = subprocess.check_output(["git", "remote", "get-url", "origin"])
    out = subprocess.check_output(["git", "ls-remote", "--exit-code", "-h"])
    return not ("fatal" in str(out)), str(current_url)

def check_ue4_file_association():
    file_assoc_result = subprocess.getoutput(["assoc", ".uproject"])
    return "Unreal.ProjectFile" in file_assoc_result

def run_pbget():
    os.chdir("PBGet")
    subprocess.call(["PBGet.exe", "resetcache"])
    status = subprocess.call(["PBGet.exe", "pull", "--threading", "false"])
    os.chdir("..")
    return status

def check_running_process(process_name):
    if process_name in (p.name() for p in psutil.process_iter()):
        return True
    return False

def run_ue4versionator():
    if PBParser.is_versionator_symbols_enabled():
        return subprocess.call(["ue4versionator.exe", "--with-symbols"])
    else:
        return subprocess.call(["ue4versionator.exe"])

def clean_old_engine_installations():
    current_version = PBParser.get_engine_version_with_prefix()
    if current_version != None:
        engine_install_root = PBParser.get_engine_install_root()
        if engine_install_root != None and os.path.isdir(engine_install_root):
            dirs = os.listdir(engine_install_root)
            for dir in dirs:
                if dir != current_version:
                    full_path = os.path.join(engine_install_root, dir)
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
# 3: DDC generation was successful, but version file update was not successful
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
                if not PBParser.ddc_update_version():
                    return 3, err
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