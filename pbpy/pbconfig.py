import os
import sys
from xml.etree.ElementTree import parse

# Singleton Config
config = None


def get(key):
    if key is None or config is None or config.get(str(key)) is None:
        print(f"Invalid config get request: {key}")
        sys.exit(1)

    return config.get(str(key))


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
        is_ci = os.environ.get('PBSYNC_CI', None) is not None

        config["is_ci"] = is_ci

        return True

    return False
