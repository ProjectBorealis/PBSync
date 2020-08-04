python -m pip install -U pip
pip install -Ur requirements.txt
set PYTHONOPTIMIZE=1
pyinstaller --noupx --onefile --additional-hooks-dir=hooks -n PBSync --clean --icon=resources/icon.ico --version-file version.rc -p pbpy:pbsync pbsync/pbsync.py
