import subprocess
import os.path
import os
import sys
from zipfile import ZipFile

from pbpy import pblog

hub_executable_path = "hub\\hub.exe"
binary_package_name = "Binaries.zip"

def pull_binaries(version_number: str):
    try:
        ret = subprocess.call([hub_executable_path, "release", "download", version_number, binary_package_name])
        if ret != 0:
            return False
    except:
        return False

    try:
        with ZipFile(binary_package_name, 'r') as zip_file:
            # TODO: Do checksum
            zip_file.extractall()
    except:
        return False