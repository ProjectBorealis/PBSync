git submodule update --init
cd pyinstaller\bootloader
python waf all
cd ..
python setup.py install
cd ..
