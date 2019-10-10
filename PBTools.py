import os
import os.path
import psutil
import subprocess
import shutil
import time

# PBSync Imports
import PBParser

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

def generate_ddc_data():
    current_version = PBParser.get_engine_version_with_prefix()
    
    if current_version != None:
        engine_install_root = PBParser.get_engine_install_root()
        installation_dir = os.path.join(engine_install_root, current_version)
        if os.path.isdir(installation_dir):
            ue_editor_executable = os.path.join(installation_dir, "Engine/Binaries/Win64/UE4Editor.exe")
            if os.path.isfile(ue_editor_executable):
                subprocess.call([str(ue_editor_executable), os.path.join(os.getcwd(), "ProjectBorealis.uproject"), "-run=DerivedDataCache", "-fill"])
                return PBParser.ddc_update_version()
    
    return False