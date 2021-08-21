from flexx import flx

class SettingsWidget(flx.Widget):
    
    def init(self):
        with flx.VBox():
            with flx.HBox():
                with flx.VBox():
                    flx.Label(text='UE Download Folder')
                    flx.Label(text='Project Version')
                    self.symbols = flx.CheckBox(text="Download Symbols")
                    self.autosync = flx.CheckBox(text="Always Auto-Sync")
                    self.legacy = flx.CheckBox(text="Force Legacy Engine Archives")
                    flx.Label(text='Git exe')
                    flx.Label(text='Git LFS exe')
                with flx.VBox():
                    self.download = flx.LineEdit(placeholder_text="Folder to download Unreal Engine to", minsize=(400, 28), flex=1)
                    self.version = flx.LineEdit(text="latest", flex=1)
                    flx.Widget(flex=1, minsize=(10, 28))
                    flx.Widget(flex=1, minsize=(10, 28))
                    flx.Widget(flex=1, minsize=(10, 28))
                    self.exe_git = flx.LineEdit(placeholder_text="Custom Git exe to use instead of the default", minsize=(500, 28), flex=1)
                    self.exe_git = flx.LineEdit(placeholder_text="Custom Git LFS exe to use instead of the default", minsize=(500, 28), flex=1)
            with flx.GroupWidget(title="Launch App"):
                with flx.VBox():
                    self.launch_editor = flx.RadioButton(text="Unreal Editor", checked=True)
                    self.launch_vs = flx.RadioButton(text="Visual Studio")
                    self.launch_rider = flx.RadioButton(text="Rider")
                    self.launch_non = flx.RadioButton(text="None")
            with flx.GroupWidget(title="Engine Bundle"):
                with flx.VBox():
                    self.bundle_editor = flx.RadioButton(text="Editor (development only)", checked=True)
                    self.bundle_engine = flx.RadioButton(text="Engine (can package game)")
