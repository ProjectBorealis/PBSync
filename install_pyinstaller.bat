@echo off
git submodule update --init
.\dependencies.bat
cd pyinstaller\bootloader
python ./waf all
cd ..
python setup.py install
cd ..
