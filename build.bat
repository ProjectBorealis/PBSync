@echo off
set PYTHONOPTIMIZE=1
set PYTHONHASHSEED=0
pyinstaller --onefile ^
            --additional-hooks-dir=hooks ^
            -n PBSync ^
            --clean ^
            -i resources/icon.ico ^
            --version-file version.rc ^
            -p pbpy:pbsync pbsync/__main__.py
