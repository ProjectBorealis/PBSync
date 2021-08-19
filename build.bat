@echo off
set PYTHONOPTIMIZE=1
pyinstaller --onefile ^
            --noupx ^
            --additional-hooks-dir=hooks ^
            -n PBSync ^
            --clean ^
            -i resources/icon.ico ^
            --version-file version.rc ^
            -p pbpy:pbsync pbsync/pbsync.py
