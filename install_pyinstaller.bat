@echo off
git submodule update --init
cd pyinstaller
setlocal
set PYINSTALLER_COMPILE_BOOTLOADER="1"
python setup.py install
cd ..
