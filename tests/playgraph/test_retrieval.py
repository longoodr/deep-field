from typing import Iterable, Tuple

import networkx as nx
import pytest

from deepfield.dbmodels import Play
from deepfield.playgraph.retrieval import PlayGraphPersistor
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import utils


def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()

class TestPersistence:

    @classmethod
    def setup_class(cls):
        utils.clean_db()

    def test_consistency(self):
        p = PlayGraphPersistor()
        for db_modification in [
            lambda: None,
            utils.insert_natls_game,
            utils.insert_cubs_game,
            lambda: Play.get().delete_instance()
        ]:
            db_modification()
            assert not p.is_consistent()
            rewritten = p.ensure_consistency()
            assert rewritten
            assert p.is_consistent()