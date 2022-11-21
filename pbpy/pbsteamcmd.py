from pathlib import Path

from pbpy import pblog, pbtools, pbconfig

def publish_build(branch_type, steamcmd_exec_path, publish_stagedir, steamcmd_script):
  # Test if our configuration values exist
  if not steamcmd_script:
    pblog.error("steamcmd was not configured.")
    return False

  script_path = (Path() / steamcmd_script).resolve()

  proc = pbtools.run([steamcmd_exec_path, "+login", pbconfig.get_user("steamcmd", "username"), pbconfig.get_user("steamcmd", "password"), "+run_app_build", script_path, "+quit"])
  result = proc.returncode
  return result
