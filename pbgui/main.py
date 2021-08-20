from pbgui.core import Core
from flexx import flx
import pbgui
import logging
import flexx
import threading

flexx.config.log_level = logging.INFO


def run_flexx():
    a = flx.App(Core, title='PBSync')
    pbgui.m = a.launch(runtime='chrome-app')


def startup():
    pass


def run():
    run_flexx()

    startup_thread = threading.Thread(target=startup)
    startup_thread.start()

    flx.start()
    startup_thread.join()
