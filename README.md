# PBSync

Advanced workspace synchronization tool for Unreal Engine projects hosted on git repositories.

## Setup

PyInstaller is required for executable generation, and it should be built from source to prevent false positive virus detections of generated PBSync executable.

- Clone https://github.com/pyinstaller/pyinstaller
- In bootloader folder, run `./waf all` command. This will generate bootloader files by using your system. This highly decreases false positive virus detection probability of your generated PBSync.exe
- On pyinstaller folder, run `python setup.py install`

## Distribution

To generate a binary file from python source code, just run `build.bat` script. If generation was successful, the binary file will be put inside `dist` folder. To start using, generated executable should be put into root folder of the Unreal Engine project.

You must use Python 3.7, as [Python 3.8 is not yet supported by PyInstaller](https://github.com/pyinstaller/pyinstaller/issues/4311).

## Available Commands

List of available commands can be printed to console by passing `--help` to generated executable.

## Copyright & Contribution

Everyone is welcomed to fork the repository, or open pull requests & new issues in this main repository.

```
MIT License

Copyright (c) 2019-2020 Project Borealis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
