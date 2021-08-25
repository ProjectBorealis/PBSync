import os

from pbpy import pblog, pbtools, pbconfig

# DISPATCH_APP_ID: App ID. env. variable for dispatch application
# DISPATCH_INTERNAL_BID: Branch ID env. variable for internal builds
# DISPATCH_PLAYTESTER_BID: Branch ID env. variable for playtester builds


def push_build(branch_type, dispath_exec_path, dispatch_config, dispatch_stagedir):
    # Test if our configuration values exist
    app_id = pbconfig.get_user('dispatch', 'app_id')
    if app_id is None or app_id == "":
        pblog.error("dispatch.app_id was not configured.")
        return False

    if branch_type == "internal":
        branch_id_key = 'internal_bid'
    elif branch_type == "playtester":
        branch_id_key = 'playtester_bid'
        pblog.error("Playtester builds are not allowed at the moment.")
        return False
    else:
        pblog.error("Unknown Dispatch branch type specified.")
        return False

    branch_id = pbconfig.get_user('dispatch', branch_id_key)
    if branch_id is None or branch_id == "":
        pblog.error(f"{branch_id_key} was not configured.")
        return False

    # Push and Publish the build
    proc = pbtools.run([dispath_exec_path, "build", "push", branch_id, dispatch_config, dispatch_stagedir, "-p"])
    result = proc.returncode
    return result == 0
