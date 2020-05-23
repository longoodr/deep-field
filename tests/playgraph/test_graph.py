from typing import Tuple

import pytest

from deepfield.playgraph.builder import PlayGraphBuilder
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.dbmodels import Play
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import test_env


class TestBuilder:

    URL = "WAS201710120.shtml"

    @classmethod
    def setup_class(cls):
        link = BBRefLink(cls.URL)
        page = Page.from_link(link)
        test_env.insert_mock_players(page)
        ScrapeNode.from_page(page).scrape()

    def test_builder(self):
        graph = PlayGraphBuilder().get_graph()
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
        for u, v in map(self.__play_nums_to_id, included_edges):
            assert graph.has_edge(u, v)
        for u, v in map(self.__play_nums_to_id, excluded_edges):
            assert not graph.has_edge(u, v)

    @classmethod
    def __play_nums_to_id(cls, play_nums: Tuple) -> Tuple:
        return tuple([cls.__play_num_to_id(pnum) for pnum in play_nums])

    @classmethod
    def __play_num_to_id(cls, play_num: int) -> int:
        return Play.get(Play.play_num == play_num).id
