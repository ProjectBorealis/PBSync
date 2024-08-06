import shutil
from pathlib import Path

from pbpy import pbconfig, pblog, pbtools


def publish_build(
    branch_type,
    steamcmd_exec_path,
    publish_stagedir,
    app_script,
    drm_app_id,
    drm_exe_path,
    drm_useonprem,
):
    # Test if our configuration values exist
    if not app_script:
        pblog.error("steamcmd was not configured.")
        return False

    # The basic needed command line to get into steamcmd
    base_steamcmd_command = [
        steamcmd_exec_path,
        "+login",
        pbconfig.get_user("steamcmd", "username"),
        pbconfig.get_user("steamcmd", "password"),
    ]

    def steam_log(log):
        log = log.rstrip()
        if not log:
            return
        pblog.info("[steamcmd] " + log)

    # if drm wrapping is configured
    nondrm_bytes = None
    if drm_app_id and drm_exe_path:
        drm_exe_path = Path(drm_exe_path)
        if not drm_exe_path.is_absolute():
            drm_exe_path = (
                Path(pbconfig.config_filepath).parent / drm_exe_path
            ).resolve()
        if not drm_exe_path.is_file():
            pblog.error("steamcmd/drm/targetbinary does not exist.")
            return False
        drm_command = base_steamcmd_command.copy()
        drm_output = (
            Path(pbconfig.config_filepath).parent
            / Path("wrappedBin" + drm_exe_path.suffix)
        ).resolve()  # save file to wrappedBin.exe temporarily
        drm_command.extend(
            [
                "+drm_wrap",
                drm_app_id,
                str(drm_exe_path),
                str(drm_output),
                "drmtoolp",
                "6",
                "local" if drm_useonprem else "cloud",
                "+quit",
            ]
        )  # the drm wrap command https://partner.steamgames.com/doc/features/drm
        pblog.info("Wrapping game with Steamworks DRM...")
        drm_proc = pbtools.run_stream(drm_command, logfunc=steam_log)
        if drm_proc.returncode != 0:
            if drm_output.exists():
                pbtools.remove_file(str(drm_output))
            pbtools.error_state(
                f"DRM wrapping failed: exit code {drm_proc.returncode}",
                hush=True,
                term=True,
            )
            return False

        with open(drm_exe_path, "wb") as orig_file:
            nondrm_bytes = orig_file.read()
        pbtools.remove_file(str(drm_exe_path))  # remove original file on success
        shutil.move(
            str(drm_output), str(drm_exe_path)
        )  # move drm-wrapped file to location of original
    else:
        drm_exe_path = None

    script_path = (Path() / app_script.format(branch_type)).resolve()
    build_cmd = base_steamcmd_command.copy()
    build_cmd.extend(["+run_app_build", script_path, "+quit"])
    proc = pbtools.run_stream(build_cmd, logfunc=steam_log)
    result = proc.returncode

    if drm_exe_path and drm_exe_path.is_file():
        # remove drm wrapped file and write the original file, so that a subsequent build will re-build a non-wrapped executable
        pbtools.remove_file(drm_exe_path)
        with open(drm_exe_path, "wb") as orig_file:
            orig_file.write(nondrm_bytes)

    return result
