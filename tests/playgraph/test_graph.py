from typing import Iterable, Tuple

import pytest

from deepfield.playgraph.builder import _PlayGraphBuilder
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.dbmodels import Play
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import test_env


def setup_module(module):
    test_env.init_test_env()

def teardown_module(module):
    test_env.delete_db_file()

class UseGamePlays:

    urls: Iterable[str]

    @classmethod
    def setup_class(cls):
        for url in cls.urls:
            cls._add_game(url)

    @staticmethod
    def _add_game(url: str) -> None:
        link = BBRefLink(url)
        page = Page.from_link(link)
        test_env.insert_mock_players(page)  # type: ignore
        ScrapeNode.from_page(page).scrape()

class TestBuilder(UseGamePlays):

    urls = [
            "WAS201710120.shtml"
        ]
        
    def test_builder(self):
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

def _play_num_to_id(play_num: int) -> int:
    return Play.get(Play.play_num == play_num).id

def _play_nums_to_id(play_nums: Tuple) -> Tuple:
    return tuple([_play_num_to_id(pnum) for pnum in play_nums])
