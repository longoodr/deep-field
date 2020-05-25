from typing import Iterable, Tuple

import networkx as nx
import pytest

from deepfield.dbmodels import Play
from deepfield.playgraph.getters import PlayGraphPersistor, PlayGraphBuilder
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import utils


def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()

class TestBuilder:

    @classmethod
    def setup_class(cls):
        utils.clean_db()
        
    def test_builder(self):
        utils.insert_game("WAS201710120.shtml")
        graph = PlayGraphBuilder().get_graph()
        included_edges = [
            (0, 2),
            (2, 3),
            (7, 13),
        ]
        excluded_edges = [
            (1, 2),
            (0, 3),
            (1, 3),
            (7, 8),
            (10, 11)
        ]
        for u, v in map(_play_nums_to_id, included_edges):
            assert graph.has_edge(u, v)
        for u, v in map(_play_nums_to_id, excluded_edges):
            assert not graph.has_edge(u, v)

class TestPersistence:

    p: PlayGraphPersistor

    @classmethod
    def setup_class(cls):
        cls.p = PlayGraphPersistor()

    @classmethod
    def teardown_class(cls):
        cls.p.remove_files()

    def setup_method(self, _):
        self.p.remove_files()
        utils.clean_db()

    def test_no_file_returns_none(self):
        assert self.p._get_on_disk_graph() is None

    def test_graph_save(self):
        utils.insert_natls_game()
        g1 = self.p.get_graph()
        g2 = self.p._get_on_disk_graph()
        assert nx.is_isomorphic(g1, g2)

    def test_od_consistency(self):
        self.p.get_graph()
        assert self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is not None
        utils.insert_cubs_game()
        assert not self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is None
        self.p.get_graph()
        assert self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is not None
        self.p.get_graph()
        assert self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is not None
        with open(self.p._hash_filename, "a") as hash_file:
            hash_file.write("bad data")
        assert not self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is None
        self.p.get_graph()
        assert self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is not None
        Play.get().delete_instance()
        assert not self.p.is_on_disk_consistent()
        assert self.p._get_on_disk_graph() is None

def _play_num_to_id(play_num: int) -> int:
    return Play.get(Play.play_num == play_num).id

def _play_nums_to_id(play_nums: Tuple) -> Tuple:
    return tuple([_play_num_to_id(pnum) for pnum in play_nums])