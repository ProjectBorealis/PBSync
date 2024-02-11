from pathlib import Path

from pbpy import pblog, pbtools, pbconfig

def publish_build(branch_type, steamcmd_exec_path, publish_stagedir, app_script):
  # Test if our configuration values exist
  if not app_script:
    pblog.error("steamcmd was not configured.")
    return False

  script_path = (Path() / app_script.format(branch_type)).resolve()

  proc = pbtools.run([steamcmd_exec_path, "+login", pbconfig.get_user("steamcmd", "username"), pbconfig.get_user("steamcmd", "password"), "+run_app_build", script_path, "+quit"])
  result = proc.returncode
  return result
