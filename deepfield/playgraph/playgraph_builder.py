import argparse

from deepfield.dbmodels import init_db
from deepfield.playgraph.getters import PlayGraphPersistor
from deepfield.script_utils import config_logging, logger
from deepfield.playgraph.graph import GraphLayerer

def main():
    parser = argparse.ArgumentParser(
            description = "Reads plays from the database and saves a play dependency graph to it."
        )
    config_logging()
    init_db()
    persistor = PlayGraphPersistor()
    if persistor.is_on_disk_consistent():
        logger.info("Graph already built")
    else:
        persistor.get_graph()
        logger.info("Graph built")
    for layer in GraphLayerer(persistor.get_graph()).get_layers():
            logger.info(len(layer))

if __name__ == "__main__":
    main()
