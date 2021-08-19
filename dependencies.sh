#!/bin/sh

# This is where Python executables install if not installed system-wide
PATH="$HOME/.local/bin:$PATH"

export PATH

python -m pip install -U pip
pip install -Ur requirements-linux.txt
