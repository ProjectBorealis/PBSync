import platform

from pathlib import Path
import shutil

from pbpy import pblog, pbtools, pbunreal


def publish_build(branch_type, butler_exec_path, publish_stagedir, butler_project, butler_manifest):
    # Test if our configuration values exist
    if not butler_project or not butler_manifest:
        pblog.error("butler was not configured.")
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

    manifest_path = Path(publish_stagedir) / ".itch.toml"

    shutil.copyfile(butler_manifest.format(plat), manifest_path)

    channel = f"{branch_type}-{plat}"

    # Push and Publish the build
    proc = pbtools.run([butler_exec_path, "push", publish_stagedir, f"{butler_project}:{channel}", "--userversion", pbunreal.get_project_version()])
    result = proc.returncode
    manifest_path.unlink()
    return result
