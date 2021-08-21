from pbgui.core import Core
from flexx import flx
import pbgui
import logging
import flexx
import threading

flexx.config.log_level = logging.INFO


def run_flexx():
    a = flx.App(Core, title='PBSync')
    pbgui.m = a.launch(runtime='chrome-browser')


def startup():
    pass


def run(sync):
    pbgui.sync_fn = sync
    run_flexx()

    startup_thread = threading.Thread(target=startup)
    startup_thread.start()

    flx.start()
    # in case we exit before startup is finished
    startup_thread.join()
