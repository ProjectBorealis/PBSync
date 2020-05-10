import os
import subprocess

from pbpy import pblog

default_drm_exec_name = "ProjectBorealis.exe"
exec_max_allowed_size = 104857600  # 100mb

# DISPATCH_APP_ID: App ID. env. variable for dispatch application
# DISPATCH_INTERNAL_BID: Branch ID env. variable for internal builds
# DISPATCH_PLAYTESTER_BID: Branch ID env. variable for playtester builds


def push_build(branch_type, dispath_exec_path, dispatch_config, dispatch_stagedir, dispatch_apply_drm_path):
    # Test if our environment variables exist
    app_id = os.environ.get('DISPATCH_APP_ID')
    if app_id is None or app_id == "":
        pblog.error("DISPATCH_APP_ID was not defined in the system environment.")
        return False

    if branch_type == "internal":
        branch_id_env = 'DISPATCH_INTERNAL_BID'
    elif branch_type == "playtester":
        branch_id_env = 'DISPATCH_PLAYTESTER_BID'
    else:
        pblog.error("Unknown Dispatch branch type specified.")
        return False

    branch_id = os.environ.get(branch_id_env)
    if branch_id is None or branch_id == "":
        pblog.error(f"{branch_id_env} was not defined in the system environment.")
        return False

    executable_path = None
    for file in os.listdir(dispatch_apply_drm_path):
        if file.endswith(".exe"):
            executable_path = os.path.join(dispatch_apply_drm_path, str(file))

    if executable_path is None:
        pblog.error(f"Executable {dispatch_apply_drm_path} not found while attempting to apply DRM wrapper.")
        return False

    if os.path.getsize(executable_path) > exec_max_allowed_size:
        executable_path = dispatch_apply_drm_path
        for i in range(3):
            executable_path = os.path.join(executable_path, "..")
        executable_path = os.path.abspath(executable_path)
        executable_path = os.path.join(executable_path, default_drm_exec_name)

    # Wrap executable with DRM
    result = subprocess.run([dispath_exec_path, "build", "drm-wrap", app_id, executable_path]).returncode
    if result != 0:
        return False

    # Push & Publish the build
    result = subprocess.run([dispath_exec_path, "build", "push",
                             branch_id, dispatch_config, dispatch_stagedir, "-p"]).returncode
    return result == 0
