import sys
import logging

from pbpy import pbtools
from pbpy import pbconfig

def setup_logger(log_file_path):
  logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s", datefmt='%d-%b-%y %H:%M:%S')
  fileHandler = logging.FileHandler(log_file_path)
  fileHandler.setFormatter(logFormatter)
  logging.getLogger().addHandler(fileHandler)
  consoleHandler = logging.StreamHandler()
  consoleHandler.setFormatter(logFormatter)
  logging.getLogger().addHandler(consoleHandler)
  logging.getLogger().setLevel(logging.DEBUG)

def error(msg):
  logging.error(msg)

def warning(msg):
  logging.warning(msg)

def info(msg):
  logging.info(msg)

def debug(msg):
  logging.debug(msg)