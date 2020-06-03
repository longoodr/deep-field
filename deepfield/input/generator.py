import argparse
import logging

from deepfield.script_utils import config_logging, logger
from deepfield.dbmodels import init_db
from deepfield.input.writing import InputDataPersistor


def main():
    parser = argparse.ArgumentParser(description="Generates input data from plays in the database.")
    config_logging()
    init_db()
    p = InputDataPersistor()
    if p.is_consistent():
        logger.info("Data already exists")
        return
    logger.info("Writing data...")
    p.ensure_consistency()
    logger.info("Data successfully written")

if __name__ == "__main__":
    main()