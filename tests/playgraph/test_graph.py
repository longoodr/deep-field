from tests import utils
from deepfield.playgraph.graph import GraphLayerer
from deepfield.playgraph.getters import PlayGraphBuilder

import pytest

def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()

class TestLayerer:
    
    @classmethod
    def setup_class(cls):
        utils.insert_natls_game()
        graph = PlayGraphBuilder().get_graph()
        cls.layerer = GraphLayerer(graph)

    @classmethod
    def teardown_class(cls):
        utils.clean_db()

    def test_layers(self):
        expected_in = [
            (1, 9),
            (3, 11),
            (4, 13),
            (5,),
            (6,),
            (7,),
            (8,),
            (14,),
        ]
        for layer, e_in in zip(
                self.layerer.get_layers(),
                expected_in
            ):
            for exp in e_in:
                assert exp in layer