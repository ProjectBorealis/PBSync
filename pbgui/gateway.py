from flexx import flx
from pscript import RawJS

import importlib.resources as pkg_resources
import gui
import gui.js
import gui.css
import gui.templates

from pbgui import load_static, load_template, widgets

pages = {}


def load_templated_page(file, name, kwargs):
    print(f"Loaded template {file}.html ({name})")
    pages[name] = load_template(f"{file}.html", kwargs)

# Base HTML page name -> list of virtual page names
virtual_pages = {
}

# Jinja2 static properties to define per page
page_props = {
    "d": {},
    "sync": {
        "name": "Sync"
    },
    "settings": {
        "name": "Settings"
    }
}

for resource in pkg_resources.contents(gui.templates):
    if "." not in resource:
        continue
    with pkg_resources.path(gui.templates, resource) as page:
        vpages = [page.stem]
        if page.stem in virtual_pages:
            vpages.extend(virtual_pages[page.stem])
        for vpage in vpages:
            if page.is_file() and page.suffix == ".html":
                props = page_props["d"]
                if vpage in page_props:
                    props = {**props, **page_props[vpage]}
                props["PAGE"] = vpage
                load_templated_page(page.stem, vpage, props)

flx.assets.associate_asset("pbgui.gateway", "js/app.js", lambda: load_static(gui.js, "app.js"))

remote_assets = ["https://cdn.jsdelivr.net/npm/bootstrap@5.1.0/dist/css/bootstrap.min.css", "https://cdn.jsdelivr.net/npm/bootstrap@5.1.0/dist/js/bootstrap.bundle.min.js"]

for url in remote_assets:
    flx.assets.associate_asset("pbgui.gateway", url)


class Gateway(flx.Label):
    CSS = load_static(gui.css, "font-awesome.css") + load_static(gui.css, "app.css")

    actions = {}

    elements = {}

    page_elements = []

    widgets = {}

    jfs = None

    def init(self):
        self.actions = {
            "change_page": self.change_page,
            "app_update": self.app_update,
        }
        self.elements = {
            "Button": flx.Button,
            "FileWidget": None,
            "CommitLogTable": widgets.CommitLogTableWidget,
            "Settings": widgets.SettingsWidget,
        }

    def _create_dom(self):
        return flx.create_element("div", {"id": "app", "onreact": self.react})

    def _render_dom(self):
        return None

    def react(self, action, *data):
        if action in self.actions:
            return self.actions[action](*data)
        else:
            print(f"{action} not found!")

    def change_page(self, page):
        for element in self.page_elements:
            element.outernode.remove()
            element.dispose()
        self.page_elements.clear()
        self.widgets.clear()
        self.set_html(pages[page])

    def get_widget(self, element_id):
        return self.widgets[element_id]

    def app_update(self):
        global window
        flexx_elements = window.document.querySelectorAll("x-flx")
        construct = RawJS("Reflect.construct")
        self.__enter__()
        for i in flexx_elements:
            element = flexx_elements[i]
            el_name = element.getAttribute("el")
            if el_name in self.elements:
                kwargs = {}
                for data in element.dataset:
                    kwargs[data] = element.dataset[data]
                flx_node = None
                if el_name == "FileWidget":
                    flx_node = self.jfs
                else:
                    constructor = self.elements[el_name]
                    flx_node = construct(constructor, [{"flx_args": [], "flx_kwargs": kwargs}])
                    self.page_elements.append(flx_node)
                element_id = element.getAttribute("id")
                if element_id is not None:
                    self.widgets[element_id] = flx_node
                    flx_node.outernode.id = element_id
                element.after(flx_node.outernode)
                element.remove()
        self.__exit__()

    @flx.action
    def set_jfs(self, filebrowser):
        self.jfs = filebrowser

    @flx.action
    def update_commits(self, commits):
        self.get_widget("commit-log").update_commits(commits)

    @flx.action
    def init_page(self, page):
        self.set_html(pages[page])
