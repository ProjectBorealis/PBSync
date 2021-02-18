#!/bin/sh

# This is where Python executables install if not installed system-wide
PATH="$HOME/.local/bin:$PATH"

export PATH

python -m pip install -U pip
pip install -Ur requirements-linux.txt
set PYTHONOPTIMIZE=1
pyinstaller --onefile \
            --additional-hooks-dir=hooks \
            -n PBSync \
            --clean \
            -i resources/icon.ico \
            --version-file version.rc \
            -p pbpy:pbsync pbsync/pbsync.py
