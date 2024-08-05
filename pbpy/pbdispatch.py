from pbpy import pblog, pbtools, pbconfig

# DISPATCH_APP_ID: App ID. env. variable for dispatch application
# DISPATCH_INTERNAL_BID: Branch ID env. variable for internal builds
# DISPATCH_PLAYTESTER_BID: Branch ID env. variable for playtester builds


def publish_build(branch_type, dispath_exec_path, publish_stagedir, dispatch_config):
    # Test if our configuration values exist
    app_id = pbconfig.get_user("dispatch", "app_id")
    if not app_id or not dispatch_config:
        pblog.error("dispatch was not configured.")
        return False

    if branch_type == "default":
        branch_type = "internal"

    branch_id_key = f"{branch_type}_bid"
    branch_id = pbconfig.get_user("dispatch", branch_id_key)
    if branch_id is None or branch_id == "":
        pblog.error(f"{branch_id_key} was not configured.")
        return False

    # Push and Publish the build
    retry = True
    while True:
        proc = pbtools.run(
            [
                dispath_exec_path,
                "build",
                "push",
                branch_id,
                dispatch_config,
                publish_stagedir,
                "-p",
            ]
        )
        result = proc.returncode
        if result != 0:
            if not retry:
                break
            # maybe we failed because of a login error. try refreshing login, and retry anyway.
            retry = False
            # refresh login state
            pbtools.run([dispath_exec_path, "login"])
            # actually log in
            pbtools.run([dispath_exec_path, "login"])
        else:
            break
    return result
