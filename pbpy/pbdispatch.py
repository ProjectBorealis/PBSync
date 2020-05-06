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
    try:
        test = str(os.environ['DISPATCH_APP_ID'])
    except Exception as e:
        pblog.exception(str(e))
        pblog.error("DISPATCH_APP_ID is not found in environment variables")
        return False

    if branch_type == "internal":
        try:
            test = str(os.environ['DISPATCH_INTERNAL_BID'])
        except Exception as e:
            pblog.exception(str(e))
            pblog.error(
                "DISPATCH_INTERNAL_BID is not found in environment variables")
            return False
    elif branch_type == "playtester":
        try:
            test = str(os.environ['DISPATCH_PLAYTESTER_BID'])
        except Exception as e:
            pblog.exception(str(e))
            pblog.error(
                "DISPATCH_PLAYTESTER_BID is not found in environment variables")
            return False

    executable_path = None
    for file in os.listdir(dispatch_apply_drm_path):
        if file.endswith(".exe"):
            executable_path = os.path.join(dispatch_apply_drm_path, str(file))

    if executable_path is None:
        pblog.error("Executable {0} not found while attempting to apply DRM wrapper.".format(dispatch_apply_drm_path))
        return False

    if os.path.getsize(executable_path) > exec_max_allowed_size:
        executable_path = dispatch_apply_drm_path
        for i in range(3):
            executable_path = os.path.join(executable_path, "..")
        executable_path = os.path.abspath(executable_path)
        executable_path = os.path.join(executable_path, default_drm_exec_name)

    # Wrap executable with DRM
    result = subprocess.call([dispath_exec_path, "build", "drm-wrap",
                              str(os.environ['DISPATCH_APP_ID']), executable_path])
    if result != 0:
        return False

    branch_id = "-1"
    if branch_type == "internal":
        branch_id = str(os.environ['DISPATCH_INTERNAL_BID'])
    elif branch_type == "playtester":
        branch_id = str(os.environ['DISPATCH_PLAYTESTER_BID'])
    else:
        return False

    # Push & Publish the build
    result = subprocess.call([dispath_exec_path, "build", "push",
                              branch_id, dispatch_config, dispatch_stagedir, "-p"])
    return result == 0
