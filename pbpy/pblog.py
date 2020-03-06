import sys
import logging
import os.path

from pbpy import pbtools
from pbpy import pbconfig

max_log_size = 10485760

def setup_logger(log_file_path):
   # If log file is big enough, remove it
  if os.path.isfile(log_file_path) and os.path.getsize(log_file_path) >= max_log_size:
      pbtools.remove_file(log_file_path)

  # Prepare logger
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
