import logging
import os.path
import sys

import coloredlogs
import verboselogs

from pbpy import pbtools

max_log_size = 5 * 1000 * 1000


def setup_logger(log_file_path):
    # If log file is big enough, remove it
    if os.path.isfile(log_file_path) and os.path.getsize(log_file_path) >= max_log_size:
        pbtools.remove_file(log_file_path)

    # Prepare logger
    verboselogs.install()

    # Formatting
    format_string = "%(asctime)s [%(levelname)-5.5s]  %(message)s"
    date_format = '%d-%b-%y %H:%M:%S'
    log_formatter = logging.Formatter(format_string, datefmt=date_format)

    root_log = logging.getLogger()

    # File handler
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(log_formatter)
    root_log.addHandler(file_handler)

    # Log level
    log_level = logging.DEBUG
    root_log.setLevel(log_level)

    # Colored logs
    coloredlogs.DEFAULT_LEVEL_STYLES = {
        **coloredlogs.DEFAULT_LEVEL_STYLES,
        "trace": {"color": 246},
        "critical": {"background": "red"},
        "debug": coloredlogs.DEFAULT_LEVEL_STYLES["info"]
    }
    coloredlogs.DEFAULT_LOG_FORMAT = format_string
    coloredlogs.DEFAULT_LOG_LEVEL = log_level
    coloredlogs.DEFAULT_DATE_FORMAT = date_format
    coloredlogs.install(logger=root_log, stream=sys.stdout)


def critical(msg):
    logging.critical(msg)


def error(msg):
    logging.error(msg)


def exception(msg):
    logging.exception(msg)


def success(msg):
    logging.success(msg)


def warning(msg):
    logging.warning(msg)


def info(msg):
    logging.info(msg)


def debug(msg):
    logging.debug(msg)
