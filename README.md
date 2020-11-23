# PBSync

Advanced workspace synchronization tool for Unreal Engine projects hosted on git repositories.

## Setup

PyInstaller is required for executable generation, and it should be built from source to prevent false positive virus detections of generated PBSync executable.

- Recursive clone the repo or init the pyinstaller submodule
- In `pyinstaller/bootloader` folder, run `./waf all` command. This will generate bootloader files by using your system. This highly decreases false positive virus detection probability of your generated `PBSync.exe`
- Now, in the `pyinstaller` folder, run `python setup.py install`

## Distribution

To generate a binary file from python source code, just run `build.bat` script. If generation was successful, the binary file will be put inside `dist` folder. To start using, generated executable should be put into root folder of the Unreal Engine project.

You must use Python 3.7, as [Python 3.8 is not yet supported by PyInstaller](https://github.com/pyinstaller/pyinstaller/issues/4311).

Note: PBSync requires a modification to the gsutil dependency: remove `from gslib.tests.util import HAS_NON_DEFAULT_GS_HOST` and all usages of it from `gslib.command_runner`. You will have to do this every time gsutil updates and build again.

## Available Commands

List of available commands can be printed to console by passing `--help` to generated executable.

## Contribution

Everyone is welcomed to fork the repository, or open pull requests and new issues in this main repository.
