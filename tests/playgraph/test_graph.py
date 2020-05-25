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
            [1, 9],
            [3, 11]
        ]
        expected_out = [
            [3, 11, 2],
            [10]
        ]
        for layer, e_in, e_out in zip(
                self.layerer.get_layers(),
                expected_in,
                expected_out
            ):
            for exp in e_in:
                assert exp in layer
            for exp in e_out:
                assert exp not in layer