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
            --runtime-tmpdir Saved ^
            --key cd17c3ab10dba6bd ^
            -i resources/icon.ico ^
            --version-file version.rc ^
            -p . pbsync/__main__.py %*
