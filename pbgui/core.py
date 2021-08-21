import subprocess, os, platform

from flexx import flx
from flexx.ui import FileBrowserWidget
from pathlib import Path

from pbpy import pbgit

import pbgui
from pbgui.gateway import Gateway

class Core(flx.PyWidget):
    FilePath = ""

    def init(self):
        self.g = Gateway()
        self.fs = FileBrowserWidget()
        self.g.set_jfs(self.fs._jswidget)
        self.g.init_page(pbgui.default_page)

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

    @flx.action
    def get_commits(self):
        commits = []
        lines = pbgit.get_commits().splitlines()
        commit = None
        for line in lines:
            line = line.strip()
            need_message = True
            # start new commit entry
            if line.startswith("commit"):
                if commit:
                    commits.append(commit)
                commit = {}
                commit["sha"] = line.split(" ")[1][:8]
                commit["pass"] = "success"
            elif line.startswith("Author"):
                commit["author"] = line.split(" ")[1]
            elif line.startswith("Date"):
                time = line.split(" ", 3)[3]
                commit["time"] = time.rsplit(" ", 1)[0]
            elif line and need_message:
                commit["message"] = line
                need_message = False

        self.g.update_commits(commits)
