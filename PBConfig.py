import os
import sys
import xml.etree.ElementTree as ET

# Singleton Config
config = None

def get(key):
    if key == None or config == None or config.get(str(key)) == None:
        print("Invalid config get request: " + str(key))
        sys.exit(1)
    
    return config.get(str(key))

def generate_config(config_path):
    global config
    pbsync_version = "0.1.9"

    if config_path != None and os.path.isfile(config_path):
        tree = ET.parse(config_path)
        if tree == None:
            return False
        root = tree.getroot()
        if root == None:
            return False

        # Read config xml
        try:
            config = {
                'pbsync_version': pbsync_version,
                'engine_base_version': root.find('enginebaseversion').text,
                'supported_git_version': root.find('git/version').text,
                'supported_lfs_version': root.find('git/lfsversion').text,
                'expected_branch_name': root.find('git/expectedbranch').text,
                'git_hooks_path': root.find('git/hooksfoldername').text,
                'watchman_executable_name': root.find('git/watchmanexecname').text,
                'lfs_lock_url': root.find('git/lfslockurl').text,
                'git_url': root.find('git/url').text,
                'log_file_path': root.find('log/file').text,
                'max_log_size': int(root.find('log/maximumsize').text),
                'ddc_version_path': root.find('ddc/versionfilepath').text,
                'ddc_version': int(root.find('ddc/version').text),
                'ddc_expected_min_size': int(root.find('ddc/expectedminsize').text),
                'uproject_path': root.find('project/uprojectname').text,
                'uproject_version_key': root.find('project/uprojectversionkey').text,
                'engine_version_prefix': root.find('project/engineversionprefix').text,
                'defaultgame_path': root.find('project/defaultgameinipath').text,
                'defaultgame_version_key': root.find('project/projectversionkey').text,
                'versionator_config_path': root.find('project/versionatorconfigpath').text,
                'error_file': root.find('project/errorfile'),
                'pbget_url': root.find('pbget/url').text,
                'pbget_token': root.find('pbget/token').text
            }
        except:
            return False

        return True
        
    return False