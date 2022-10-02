import platform

from pbpy import pblog, pbtools, pbunreal


def publish_build(branch_type, butler_exec_path, publish_stagedir, butler_project):
    # Test if our configuration values exist
    if butler_project is None or butler_project == "":
        pblog.error("butler/project was not configured.")
        return False

    plat = platform.system()
    if plat == "Windows":
      plat = "win"
    elif plat == "Darwin":
      plat = "mac"
    elif plat == "Linux":
      plat = "linux"
    else:
      plat = plat.lower()

    channel = f"{branch_type}-{plat}"

    # Push and Publish the build
    proc = pbtools.run([butler_exec_path, "push", publish_stagedir, f"{butler_project}:{channel}", "--userversion", pbunreal.get_project_version()])
    result = proc.returncode
    return result
