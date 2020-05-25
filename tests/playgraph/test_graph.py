from tests import utils
from deepfield.playgraph.graph import MaximalAntichainLattice
from deepfield.playgraph.getters import PlayGraphBuilder

import pytest

def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()

class TestLattice:
    
    @classmethod
    def setup_class(cls):
        utils.insert_natls_game()
        graph = PlayGraphBuilder().get_graph()
        cls.lattice = MaximalAntichainLattice(graph)

    @classmethod
    def teardown_class(cls):
        utils.clean_db()

    def test_layers(self):
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
        for antichain, expected in zip(self.lattice, expected_layers):
            for e in expected:
                assert e in antichain