import argparse
import logging
import sys

from deepfield.dbmodels import init_db
from deepfield.playgraph.getters import PlayGraphPersistor

logger = logging.getLogger()

def main():
    parser = argparse.ArgumentParser(
            description = "Reads plays from the database and saves a play dependency graph to it."
        )
    config_logging()
    init_db()
    persistor = PlayGraphPersistor()
    if persistor.is_on_disk_consistent():
        logging.info("Graph already built")
    else:
        persistor.get_graph()
        logger.info("Graph built")

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

if __name__ == "__main__":
    main()
