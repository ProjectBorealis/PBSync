import sys
import logging
import os.path

from pbpy import pbtools

max_log_size = 5 * 1000 * 1000


def setup_logger(log_file_path):
    # If log file is big enough, remove it
    if os.path.isfile(log_file_path) and os.path.getsize(log_file_path) >= max_log_size:
        pbtools.remove_file(log_file_path)

    # Prepare logger
    log_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-5.5s]  %(message)s", datefmt='%d-%b-%y %H:%M:%S')
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(console_handler)
    logging.getLogger().setLevel(logging.DEBUG)


def error(msg):
    logging.error(msg)


def exception(msg):
    logging.exception(msg)


def warning(msg):
    logging.warning(msg)


def info(msg):
    logging.info(msg)


def debug(msg):
    logging.debug(msg)
