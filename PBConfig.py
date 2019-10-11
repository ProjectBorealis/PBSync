import os
import xml.etree.ElementTree as ET

config = None

def get_config(config_path = None):
    global config
    pbsync_version = "0.1.1"

    if config_path == None and config != None:
        return config

    if config_path != None and os.path.isfile(config_path):
        tree = ET.parse(config_path)
        if tree == None:
            return None
        root = tree.getroot()
        if root == None:
            return None

        # Read config xml
        config = {
            'pbsync_version': pbsync_version,
            'supported_git_version': root.find('version/gitversion').text,
            'supported_lfs_version': root.find('version/gitlfsversion').text,
            'engine_base_version': root.find('version/enginebaseversion').text,
            'expected_branch_name': root.find('expectedbranch').text,
            'git_hooks_path': root.find('githooksfoldername').text,
            'watchman_executable_name': root.find('watchmanexecname').text,
            'log_file_path': root.find('log/file').text,
            'max_log_size': int(root.find('log/maximumsize').text),
            'ddc_version_path': root.find('ddc/versionfilepath').text,
            'ddc_version': int(root.find('ddc/version').text),
            'uproject_path': root.find('project/uprojectname').text,
            'uproject_version_key': root.find('project/uprojectversionkey').text,
            'engine_version_prefix': root.find('project/engineversionprefix').text,
            'defaultgame_path': root.find('project/defaultgameinipath').text,
            'defaultgame_version_key': root.find('project/projectversionkey').text,
            'versionator_config_path': root.find('project/versionatorconfigpath').text,
        }

        return config
        
    return None