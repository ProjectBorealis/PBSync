set PYTHONOPTIMIZE=2 
pyinstaller --noupx --onefile -n PBSync --clean --icon=resources/icon.ico --version-file version.rc -p pbpy:pbsync pbsync/pbsync.py
