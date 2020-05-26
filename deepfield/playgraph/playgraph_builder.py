import argparse

from deepfield.dbmodels import init_db
from deepfield.playgraph.retrieval import PlayGraphPersistor
from deepfield.script_utils import config_logging, logger


def main():
    parser = argparse.ArgumentParser(
            description = "Reads plays from the database and saves the corresponding play dependency graph."
        )
    config_logging()
    init_db()
    rewritten = PlayGraphPersistor().ensure_consistency()
    if rewritten:
        logger.info("Graph built successfully")
    else:
        logger.info("Graph already built")
        

if __name__ == "__main__":
    main()
