@echo off
git submodule update --init
cd pyinstaller
setlocal
cd bootloader
python ./waf all
cd ..
pip install .
cd ..
