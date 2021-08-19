@echo off
git submodule update --init
python -m pip install -U pip
pip install -Ur pyinstaller/tests/requirements-developer.txt
cd pyinstaller\bootloader
python ./waf all
cd ..
python setup.py install
cd ..
