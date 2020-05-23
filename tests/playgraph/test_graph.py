from typing import Iterable, Tuple

import networkx as nx
import pytest

from deepfield.playgraph.builder import PlayGraphPersistor, _PlayGraphBuilder
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.dbmodels import Play
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import test_env


def setup_module(module):
    test_env.init_test_env()

def teardown_module(module):
    test_env.delete_db_file()

class TestBuilder:

    @classmethod
    def setup_class(cls):
        test_env.clean_db()
        
    def test_builder(self):
        _add_game("WAS201710120.shtml")
        graph = _PlayGraphBuilder().get_graph()
        included_edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (7, 13),
        ]
        excluded_edges = [
            (0, 2),
            (1, 3),
            (7, 8),
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
        test_env.clean_db()

    def test_no_file_returns_none(self):
        assert self.p._get_on_disk_graph() is None

    def test_graph_save(self):
        self._add_natls_game()
        g1 = self.p.get_graph()
        g2 = self.p._get_on_disk_graph()
        assert nx.is_isomorphic(g1, g2)

    def test_od_consistency(self):
        self.p.get_graph()
        assert self.p._get_on_disk_graph() is not None
        self._add_cubs_game()
        assert self.p._get_on_disk_graph() is None
        self.p.get_graph()
        assert self.p._get_on_disk_graph() is not None
        with open(self.p._graph_filename, "a") as json_file:
            json_file.write("bad data")
        assert self.p._get_on_disk_graph() is None
        self.p.get_graph()
        assert self.p._get_on_disk_graph() is not None
        with open(self.p._hash_filename, "a") as hash_file:
            hash_file.write("bad data")
        assert self.p._get_on_disk_graph() is None

    @staticmethod
    def _add_natls_game() -> None:
        _add_game("WAS201710120.shtml")

    @staticmethod
    def _add_cubs_game() -> None:
        _add_game("CHN201710110.shtml")

def _play_num_to_id(play_num: int) -> int:
    return Play.get(Play.play_num == play_num).id

def _play_nums_to_id(play_nums: Tuple) -> Tuple:
    return tuple([_play_num_to_id(pnum) for pnum in play_nums])

def _add_game(url: str) -> None:
    link = BBRefLink(url)
    page = Page.from_link(link)
    test_env.insert_mock_players(page)  # type: ignore
    ScrapeNode.from_page(page).scrape()
