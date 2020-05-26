from typing import Iterable, Tuple

import networkx as nx
import pytest

from deepfield.dbmodels import Play
from deepfield.playgraph.graph import LevelOrderTraversal
from deepfield.playgraph.retrieval import PlayGraphPersistor
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import utils


def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()
    PlayGraphPersistor().remove_files()

class TestPersistence:

    def setup_method(self, _):
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

    def test_correctness(self):
        utils.insert_natls_game()
        PlayGraphPersistor().ensure_consistency()
        t = LevelOrderTraversal()
        expected_layers = [
            (1, 9),
            (3, 11),
            (4, 13),
            (5,),
            (6,),
            (7,),
            (8,),
            (14,),
        ]
        for layer, expected_layer in zip(t, expected_layers):
            layer_ids = set([n["play_id"] for n in layer])
            for exp in expected_layer:
                assert exp in layer_ids
