@echo off
set PYTHONOPTIMIZE=1
set PYTHONHASHSEED=0
set PYI_STATIC_ZLIB=1
set OBJECT_MODE=64
pyinstaller --onefile ^
            --additional-hooks-dir=hooks ^
            -n PBSync ^
            --clean ^
            --console ^
            --icon=icon.ico ^
            --runtime-tmpdir Saved ^
            --key %random% ^
            -i resources/icon.ico ^
            --version-file version.rc ^
            -p pbpy:pbsync pbsync/__main__.py
