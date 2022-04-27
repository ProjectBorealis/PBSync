import os
import configparser
from xml.etree.ElementTree import parse
from functools import lru_cache

from pbpy import pbtools

# Singleton Config
config = None

user_config = None

def get(key):
    if key is None or config is None or config.get(str(key)) is None:
        pbtools.error_state(f"Invalid config get request: {key}", hush=True)

    return config.get(str(key))


@lru_cache()
def get_user_config_filename():
    config_key = 'ci_config' if get("is_ci") else 'user_config'
    return get(config_key)


class CustomConfigParser(configparser.ConfigParser):
    def __getitem__(self, key):
        if key != self.default_section and not self.has_section(key):
            self.add_section(key)
        return super().__getitem__(key)


class CustomInterpolation(configparser.BasicInterpolation):
    def before_get(self, parser, section: str, option: str, value: str, defaults) -> str:
        val = super().before_get(parser, section, option, value, defaults)
        if get("is_ci"):
            return os.getenv(val)
        return val


def init_user_config():
    global user_config
    user_config = CustomConfigParser(interpolation=CustomInterpolation())
    user_config.read(get_user_config_filename())


def get_user_config():
    if user_config is None:
        init_user_config()
    return user_config

def get_user(section, key, default=None):
    return get_user_config().get(section, key, fallback=default)


def shutdown():
    if not get("is_ci") and user_config is not None:
        user_filename = get_user_config_filename()
        attributes = 0
        restore_hidden = False
        if os.name == "nt" and os.path.exists(user_filename):
            import win32api, win32con
            attributes = win32api.GetFileAttributes(user_filename)
            restore_hidden = attributes & win32con.FILE_ATTRIBUTE_HIDDEN
            win32api.SetFileAttributes(user_filename, attributes & ~win32con.FILE_ATTRIBUTE_HIDDEN)
        with open(user_filename, 'w') as user_config_file:
            user_config.write(user_config_file)
        if restore_hidden:
            win32api.SetFileAttributes(user_filename, attributes)


def generate_config(config_path, parser_func):
    # Generalized config generator. parser_func is responsible with returning a valid config object
    global config

    if config_path is not None and os.path.isfile(config_path):
        tree = parse(config_path)
        if tree is None:
            return False
        root = tree.getroot()
        if root is None:
            return False

        # Read config xml
        try:
            config = parser_func(root)
        except Exception as e:
            print(f"Config exception: {e}")
            return False

        # Add CI information
        config["is_ci"] = os.getenv('PBSYNC_CI') is not None or os.getenv('CI') is not None
        config["checksum_file"] = ".checksum"

        return True

    return False
