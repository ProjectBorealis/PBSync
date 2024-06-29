from pathlib import Path

from pbpy import pblog, pbtools, pbconfig

def publish_build(branch_type, steamcmd_exec_path, publish_stagedir, app_script, drm_app_id, drm_exe_path):
  # Test if our configuration values exist
  if not app_script:
    pblog.error("steamcmd was not configured.")
    return False

  script_path = (Path() / app_script.format(branch_type)).resolve()
  
  command = [steamcmd_exec_path, "+login", pbconfig.get_user("steamcmd", "username"), pbconfig.get_user("steamcmd", "password")]
  if drm_app_id and drm_exe_path:
    if not Path.is_absolute(drm_exe_path):
      drm_exe_path = (Path(pbconfig.config_filepath).parent / drm_exe_path).resolve()
    if not Path.exists(drm_exe_path):
      pblog.error("steamcmd/drm/targetbinary does not exist.")
      return False
    command.extend(["+drm_wrap", drm_exe_path, drm_exe_path, "drmtoolp", "0"])
    pblog.info("Will use steamworks DRM")
  
  command.extend(["+run_app_build", script_path, "+quit"])
  proc = pbtools.run(command)
  result = proc.returncode
  return result
