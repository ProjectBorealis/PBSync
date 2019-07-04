import xml.etree.ElementTree as ET
import os.path
import os
import psutil
import shutil
import subprocess

def CheckRunningProcess(process_name):
    if process_name in (p.name() for p in psutil.process_iter()):
        return True
    return False

def CheckGitInstallation():
    return subprocess.call(["git", "--version"])

def CheckGitUpdate():
    subprocess.call(["git", "update-git-for-windows"])

def RunUe4Versionator():
    return subprocess.call(["ue4versionator.exe", "--with-symbols"])

def PurgeDestionation(destination):
    if os.path.islink(destination):
        try:
            os.unlink(destination)
        except:
            return False

    elif os.path.isdir(destination):
        is_junction = False

        try:
            shutil.rmtree(destination)
        except:
            is_junction = True

        if is_junction:
            try:
                os.remove(destination)
            except:
                return False
            

    elif os.path.isfile(destination):
        # Somehow it's a file, remove it
        try:
            os.remove(destination)
        except:
            return False

    return True