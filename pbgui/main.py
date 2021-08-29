from pbgui.core import Core
from flexx import flx
import pbgui
import logging
import flexx
import asyncio

flexx.config.log_level = logging.INFO


def run_flexx():
    a = flx.App(Core, title='PBSync')
    pbgui.m = a.launch(runtime='chrome-browser')


def startup():
    pass


def run(sync):
    pbgui.sync_fn = sync
    run_flexx()

    asyncio.get_event_loop().call_soon(startup)

    flx.run()
