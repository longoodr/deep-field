import argparse
import logging
import os
import sys

from pathvalidate.argparse import sanitize_filename_arg

DEFAULT_DB_NAME = "stats"

logger = logging.getLogger()

def config_logging():
    hdlr = logging.StreamHandler(sys.stdout)
    fmtr = logging.Formatter(
            fmt =     "%(asctime)s - %(message)s",
            datefmt = "%m-%d %H:%M:%S"
        )
    hdlr.setFormatter(fmtr)
    logger.addHandler(hdlr)
    hdlr = logging.FileHandler("log.log")
    fmtr = logging.Formatter(
            fmt =     "%(asctime)s - %(levelname)s - %(message)s",
            datefmt = "%m-%d %H:%M:%S"
        )
    hdlr.setFormatter(fmtr)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)

def add_db_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-db", "--database-name", type=_parse_db_name, default=DEFAULT_DB_NAME,
                        help="The name of the database to use. Defaults to 'stats'.")

def _parse_db_name(arg: str) -> str:
    db = sanitize_filename_arg(arg)
    if len(arg) == 0:
        raise argparse.ArgumentTypeError("Database name cannot be empty")
    if arg[-1] == '.' or len(os.path.splitext(db)[1]) > 0:
        raise argparse.ArgumentTypeError("Database name should not include a file extension")
    return db
