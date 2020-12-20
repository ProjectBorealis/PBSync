from flexx import flx, event, ui

class Relay(flx.Component):
    """ Global object to relay events to web.
    """

    @flx.emitter
    def update_progress(self, val):
        return dict(val=val)

# Create global relay
relay = Relay()

class Home(ui.Widget):
    def init(self):
        with ui.HBox():
            self.prog = ui.ProgressBar(flex=1, value=0, text='{percent} done')

    @relay.reaction('!update_progress')
    def _update_progress(self, *events):
        for ev in events:
            self.prog.set_value(ev.val)

class MainComponent(flx.Widget):
     def init(self):
        with flx.TabLayout():    
            Home(title='Home')

app = flx.App(MainComponent, title="PBSync")
app.launch('chrome-app')

def start_gui():
    flx.run()
