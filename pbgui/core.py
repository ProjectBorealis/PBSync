import subprocess, os, platform

import humanhash

from flexx import flx
from flexx.ui import FileBrowserWidget
from pathlib import Path

from pbpy import pbgit

import pbgui
from pbgui.gateway import Gateway

class Core(flx.PyWidget):
    FilePath = ""

    def init(self):
        user, token = pbgit.get_credentials()
        repo = pbgit.get_remote_url().replace(".git", "").replace("https://github.com/", "")
        self.g = Gateway(gh_user=user, gh_token=token, gh_repo=repo)
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
        need_message = False
        for line in lines:
            line = line.strip()
            # start new commit entry
            if line.startswith("commit"):
                if commit:
                    commits.append(commit)
                sha = line.split(" ")[1]
                commit = {"sha": sha, "human": humanhash.humanize(sha, words=2)}
            elif line.startswith("Author"):
                commit["author"] = line.split(" ", 1)[1].rsplit("<", 1)[0][:-1]
            elif line.startswith("Date"):
                time = line.split(" ", 3)[3]
                commit["time"] = time.rsplit(" ", 1)[0]
                need_message = True
            elif line and need_message:
                commit["message"] = line
                need_message = False

        self.g.update_commits(commits)
