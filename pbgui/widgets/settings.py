from flexx import flx

class SettingsWidget(flx.Widget):
    
    def init(self):
        with flx.VBox():
            with flx.Widget():
                with flx.Widget(css_class="row"):
                    with flx.Widget(css_class="col-2"):
                        flx.Label(text='UE Folder')
                    with flx.Widget(css_class="col-4"):
                        self.download = flx.LineEdit(placeholder_text="Folder to download Unreal Engine to", minsize=(400, 28))
            with flx.Widget():
                with flx.Widget(css_class="row"):
                    with flx.Widget(css_class="col-2"):
                        flx.Label(text='Project Version')
                    with flx.Widget(css_class="col-4"):
                        self.version = flx.LineEdit(text="latest")
            with flx.Widget(css_class="row"):
                self.symbols = flx.CheckBox(text="Download Symbols")
                self.autosync = flx.CheckBox(text="Always Auto-Sync")
                self.autosync = flx.CheckBox(text="Clean Up Old Engine Versions")
            with flx.GroupWidget(title="Engine Bundle"):
                with flx.VBox():
                    self.bundle_editor = flx.RadioButton(text="Editor (development only)", checked=True)
                    self.bundle_engine = flx.RadioButton(text="Engine (can package game)")
            with flx.GroupWidget(title="Launch App"):
                with flx.VBox():
                    self.launch_editor = flx.RadioButton(text="Unreal Editor", checked=True)
                    self.launch_vs = flx.RadioButton(text="Visual Studio")
                    self.launch_rider = flx.RadioButton(text="Rider")
                    self.launch_non = flx.RadioButton(text="None")
            with flx.GroupWidget(title="Download Binaries"):
                with flx.VBox():
                    self.bundle_editor = flx.RadioButton(text="If Promoted", checked=True)
                    self.bundle_engine = flx.RadioButton(text="Always")
                    self.bundle_engine = flx.RadioButton(text="Never")
            with flx.Widget(css_class="row"):
                with flx.Widget(css_class="col"):
                        flx.Label(text='Git exe')
                        self.exe_git = flx.LineEdit(placeholder_text="Custom Git exe", minsize=(500, 28))
                with flx.Widget(css_class="col"):
                        flx.Label(text='Git LFS exe')
                        self.exe_git = flx.LineEdit(placeholder_text="Custom Git LFS exe", minsize=(500, 28))
