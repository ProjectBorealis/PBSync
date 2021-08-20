import subprocess, os, platform

from flexx import flx
from flexx.ui import FileBrowserWidget
from pathlib import Path

import pbgui
from pbgui.gateway import Gateway

class Core(flx.PyWidget):
    FilePath = ""

    def init(self):
        self.g = Gateway()
        self.fs = FileBrowserWidget()
        self.g.set_jfs(self.fs._jswidget)

    @flx.action
    def open_file(self, filename):
        filepath = str(Path(filename).resolve())
        if platform.system() == 'Darwin':       # macOS
            subprocess.call(('open', filepath))
        elif platform.system() == 'Windows':    # Windows
            os.startfile(filepath)
        else:                                   # linux variants
            subprocess.call(('xdg-open', filepath))

    @flx.reaction('fs.selected')
    def fileselect(self, *events):
        sfile = events[-1]  # shows the path
        self.FilePath = sfile.filename
