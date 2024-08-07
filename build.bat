@echo off
set PYTHONUTF8=1
set PYTHONOPTIMIZE=2
set PYTHONHASHSEED=0
set PYI_STATIC_ZLIB=1
set OBJECT_MODE=64
pipenv run pyinstaller --clean PBSync.spec %*
