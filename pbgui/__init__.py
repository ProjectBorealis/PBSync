from logging import getLogger
from pathlib import Path

from flexx import flx

import importlib.resources as pkg_resources
import gui
import gui.webfonts
import gui.img

from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader('gui', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

log = getLogger(__name__)

asset_pkgs = [("webfonts/", gui.webfonts), ("img/", gui.img)]

m = None
default_page = "sync"
sync_fn = None

def load_flexx_static(data):
    for asset_dir, _ in asset_pkgs:
        data = data.replace(asset_dir, f"/flexx/data/shared/{asset_dir}/")
    return data


def load_template(filename, kwargs):
    template = env.get_template(filename)
    print(kwargs)
    return load_flexx_static(template.render(**kwargs))


def load_static(pkg, filename):
    data = pkg_resources.read_text(pkg, filename)
    return load_flexx_static(data)


def set_default_page(page):
    global default_page
    default_page = page


for asset_dir, asset_pkg in asset_pkgs:
    for asset_name in pkg_resources.contents(asset_pkg):
        # TODO hack: no folders
        if "." not in asset_name:
            continue

        print("Loaded shared asset " +
            flx.assets.add_shared_data(f"{asset_dir}{asset_name}", pkg_resources.read_binary(asset_pkg, asset_name)))
