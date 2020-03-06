import subprocess
import glob
import os.path
import os
import signal
import xml.etree.ElementTree as ET
import _winapi
import sys
import argparse
# PBGet Imports
import PBParser
import PBTools
# Multiprocessing
from multiprocessing.pool import ThreadPool
from multiprocessing import Manager
from multiprocessing import Value
from multiprocessing import cpu_count
from multiprocessing import freeze_support
# Colored Output
import colorama
from colorama import Fore, Back, Style

### Globals
pbget_version = "0.0.9"

binaries_folder_name = "Binaries"
nuget_source = ""
config_name = "PBGet.xml"

push_package_input = ""

package_ext = ".nupkg"
metadata_ext = ".nuspec"

push_timeout = 3600
error_state = Value('i', 0)
warning_state = Value('i', 0)
no_threading = False

already_installed_log = "is already installed"
successfully_installed_log = "Successfully installed"
package_not_installed_log = "is not found in the following primary"
###################################################################

### LOGGER
def log_success(message, prefix = True):
    global warning_state
    if prefix:
        print(Fore.GREEN + "SUCCESS: " + message + Style.RESET_ALL)
    else:
        print(Fore.GREEN + message + Style.RESET_ALL)

def log_warning(message, prefix = True):
    global warning_state
    warning_state = Manager().Value('i', 1)
    if prefix:
        print(Fore.YELLOW + "WARNING: " + message + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + message + Style.RESET_ALL)

def log_error(message, prefix = True):
    global error_state
    error_state = Manager().Value('i', 1)
    if prefix:
        print(Fore.RED +  "ERROR: " + message + Style.RESET_ALL)
    else:
        print(Fore.RED + message + Style.RESET_ALL)
############################################################################

### Subprocess commands
def install_package(package_id, package_version):
    output = subprocess.getoutput(["nuget.exe", "install", package_id, "-Version", package_version, "-NonInteractive"])

    fmt = '{:<25} {:<25} {:<40}'
    if already_installed_log in str(output):
        log_success(fmt.format(package_id, package_version, "Version already installed"), False)
        return True
    elif package_not_installed_log in str(output):
        log_error(fmt.format(package_id, package_version, "Not found in the repository"), False)
        return False
    elif successfully_installed_log in str(output):
        log_success(fmt.format(package_id, package_version, "Installation successful")+ Style.RESET_ALL, False)
        return True
    else:
        log_error("Unknown error while installing " + package_id + ": " + package_version, False)
        log_error("Trace log:", False)
        log_error(output, False)
        return False

    print()

def prepare_package(package_id, package_version):
    return subprocess.call(["nuget.exe", "pack", "Nuspec/" + package_id + metadata_ext, "-Version", package_version, "-NoPackageAnalysis"])

def push_package(package_full_name, source_name):
    return subprocess.call(["nuget.exe", "push", "-Timeout", str(push_timeout), "-Source", source_name, package_full_name])

def set_api_key(api_key):
    return subprocess.call(["nuget.exe", "SetApiKey", api_key])
############################################################################

### Other Functions
def push_interrupt_handler(signal, frame):
    # Cleanup
    print("Cleaning up temporary .nuget packages...")
    for nuspec_file in glob.glob("*.nupkg"):
        try:
            os.remove(nuspec_file)
            print("Removed: " + nuspec_file)
        except:
            print(Fore.RED + "Error while trying to remove temporary nupkg file: " + nuspec_file + Style.RESET_ALL)
            sys.exit(1)
    sys.exit(0)

def ignore_existing_installations(packages):
    fmt = '{:<25} {:<25} {:<40}'
    for package in packages.findall("package"):
        package_id = package.attrib['id']
        suffix = PBParser.get_suffix()
        if suffix != None:
            package_version = PBParser.get_plugin_version(package_id)
            if package_version == None:
                # If plugin is not found, default to project version.
                package_version = PBParser.get_project_version()
            package_version = package_version + "-" + suffix
            if PBTools.check_package_installation(package_id, package_version):
                log_success(fmt.format(package_id, package_version, "Version already installed"), False)
                packages.remove(package)
    return packages

def create_junction_from_package(source, destination):
    # Before creating a junction, clean the destionation path first
    if not PBTools.purge_destination(destination):
        log_error("Can't clean existing files in destionation junction point: " + destination)
       
    # Create junction from package contents to destination
    try:
        _winapi.CreateJunction(source, destination)
    except:
        log_error("Can't create junction point from " + source + " to " + destination)

def clean_package(package):
    try:
        package_id = package.attrib['id']
    except:
        log_error("Can't find id property for " + package + ". This package won't be cleaned.")
        return
    
    try:
        package_destination = os.path.join(package.attrib['destination'], binaries_folder_name)
    except:
        log_error("Can't find destination property for " + package_id + ". This package won't be cleaned.")
        return

    PBTools.clean_previous_package_installations(package_id)

    abs_destionation = os.path.abspath(package_destination)
    if not PBTools.purge_destination(abs_destionation):
        log_error("Can't clean existing files in destionation junction point: " + abs_destionation)
        return

def process_package(package):
    try:
        package_id = package.attrib['id']
    except:
        log_error("Can't find id property for " + package + ". This package won't be installed.")
        return
   
    package_version = PBParser.get_plugin_version(package_id)
    if package_version == None:
        # If plugin is not found, default to project version.
        package_version = PBParser.get_project_version()

    version_suffix = PBParser.get_suffix() 

    # Could not get suffix version, return
    if version_suffix == None:
        log_error("Can't get version suffix for " + package_id + ". This package won't be cleaned.")
        return

    package_version = package_version + "-" + version_suffix

    try:
        package_destination = os.path.join(package.attrib['destination'], binaries_folder_name)
    except:
        log_error("Can't find destination property for " + package_id + ". This package won't be installed.")
        return
    
    PBTools.clean_previous_package_installations(package_id)

    full_name = package_id + "." + package_version
    if install_package(package_id, package_version):
        create_junction_from_package(os.path.abspath(os.path.join(full_name, binaries_folder_name)), os.path.abspath(package_destination))
    else:
        # Try removing faulty junction
        PBTools.remove_faulty_junction(os.path.abspath(package_destination))

def push_from_nuscpec(nuspec_file):
    tree = ET.parse(nuspec_file)
    root = tree.getroot()

    package_id = root.find('metadata/id').text
    package_type = root.find('metadata/tags').text
    package_version = None

    if package_type == "Main":
        package_version = PBParser.get_project_version()
    elif package_type == "Plugin":
        package_version = PBParser.get_plugin_version(package_id)
    else:
        log_warning("Unknown .nuspec package tag found for " + package_id + ". Skipping...")
        return False

    if(package_version == None):
        log_warning("Could not get version for " + package_id + ". Skipping...")
        return False

    # Get engine version suffix
    suffix_version = PBParser.get_suffix()
    if suffix_version == None:
        log_error("Could not parse custom engine version from .uproject file.")
        return False

    package_full_version = package_version + "-" + suffix_version
    package_full_name = package_id + "." + package_full_version + package_ext

    # Create nupkg file
    prepare_package(package_id, package_full_version)

    # Push prepared package
    if push_package(package_full_name, nuget_source) != 0:
        if package_type == "Main":
            # Do not care about return state of plugin pushes, their versions are mostly same, and we will get version already exists error from NuGet
            log_error("Could not push main package into source: " + package_full_name)
            return False
        else:
            log_warning("Could not push plugin package into source: " + package_full_name)

    # Cleanup
    try:
        os.remove(package_full_name)
    except:
        log_warning("Cannot remove temporary nupkg file: " + package_full_name)

    log_success("Push successful: " + package_id + "." + package_full_version)

    return True
############################################################################

### Argparser Command Functions
def command_reset_cache():
    log_success("\nInitiating PBGet reset cache command...", False)
    print("\n*************************\n")
    return subprocess.call(["nuget.exe", "locals", "all", "-clear"])

def command_clean():
    log_success("\nInitiating PBGet clean command...", False)
    print("\n*************************\n")

    # Do not execute if Unreal Editor is running
    if PBTools.check_running_process("UE4Editor.exe"):
        log_error("Unreal Editor is running. Please close it before running pull command")
        sys.exit(1)

    # Parse packages xml file
    config_xml = ET.parse(config_name)
    packages = config_xml.getroot()

    if no_threading:
        for package in packages.findall("package"):
            clean_package(package)
    else:
        pool = ThreadPool(cpu_count())

        # Async process packages
        pool.map_async(clean_package, [package for package in packages.findall("package")])

        # Release threads
        pool.close()
        pool.join()

def command_pull():
    log_success("\nInitiating PBGet pull command...", False)
    print("\n*************************\n")

    # Do not execute if Unreal Editor is running
    if PBTools.check_running_process("UE4Editor.exe"):
        log_error("Unreal Editor is running. Please close it before running pull command")
        sys.exit(1)

    # Parse packages xml file
    config_xml = ET.parse(config_name)

    fmt = '{:<28} {:<37} {:<10}'
    print(fmt.format("  ~Package Name~", "~Version~", "~Result~"))
    packages = ignore_existing_installations(config_xml.getroot())

    if no_threading:
        for package in packages.findall("package"):
            process_package(package)
    else:
        # Async process packages
        pool = ThreadPool(cpu_count())
        pool.map_async(process_package, [package for package in packages.findall("package")])

        # Release threads
        pool.close()
        pool.join()

def command_push():
    log_success("\nInitiating PBGet push command...", False)
    print("\n*************************\n")

    signal.signal(signal.SIGINT, push_interrupt_handler)
    signal.signal(signal.SIGTERM, push_interrupt_handler)

    if push_package_input == "":
        # No package name provided by user
        log_success("All packages will be pushed...", False)
        # Iterate each nuspec file
        for nuspec_file in glob.glob("Nuspec/*.nuspec"):
            push_from_nuscpec(nuspec_file)
    else:
        log_success("Only " + push_package_input + " will be pushed...", False)
        push_from_nuscpec("Nuspec/" + push_package_input + ".nuspec")
############################################################################

def main():
    parser = argparse.ArgumentParser(description='PBGet v' + pbget_version)

    FUNCTION_MAP = {'pull' : command_pull, 'push' : command_push, 'clean' : command_clean, 'resetcache' : command_reset_cache}

    parser.add_argument('command', choices=FUNCTION_MAP.keys())
    parser.add_argument("--package", "-p", help="Single package name for push command. If not provided, each package having a metadata in Nuspec folder will be pushed instead")
    parser.add_argument("--apikey", "-k", help="Required api key for push command")
    parser.add_argument("--source", "-s", help="Source address for push command")
    parser.add_argument("--threading", "-t", help="[def=true, false] Use threading for specific commands")

    args = parser.parse_args()

    if args.command == "push":
        if PBTools.check_input_package(args.package):
            global push_package_input
            push_package_input = args.package
            push_package_input.replace(".nuspec", "")

        if not (args.apikey is None):
            set_api_key(args.apikey)
        else:
            log_error("An API key should be provided with --apikey argument for push command")

        if not (args.source is None):
            global nuget_source
            nuget_source = args.source
        else:
            log_error("A valid source address should be provided with --source argument for push command")
    
    if args.threading == "false":
        # Do not use threads
        no_threading = True

    if error_state.value == 1:
        log_error("PBGet " + args.command + " operation completed with errors\n")
        sys.exit(error_state.value)

    func = FUNCTION_MAP[args.command]
    func()
    
    print("\n*************************\n")
    if error_state.value == 1:
        log_error("PBGet " + args.command + " operation completed with errors\n")
    elif warning_state.value == 1:
        log_warning("PBGet " + args.command + " operation completed with warnings\n")
    else:
        log_success("PBGet " + args.command + " operation completed without errors\n")
    sys.exit(error_state.value)

if __name__ == '__main__':
    freeze_support()
    colorama.init()
    main()
