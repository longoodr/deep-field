import os
from shutil import copyfile
from typing import List

import pytest

from deepfield.scraping.bbref_pages import (BBRefLink, GamePage, PlayerPage,
                                            SchedulePage)
from deepfield.scraping.nodes import InsertableScrapeNode, ScrapeNode
from deepfield.scraping.pages import HtmlCache, Page
from tests import test_env


def setup_module(module):
    test_env.init_test_env()

def teardown_module(module):
    test_env.delete_db_file()

class TestScrapeNode:
    
    def test_from_page(self):
        link = BBRefLink("WAS201710120.shtml")
        page = Page.from_link(link)
        new_node1 = ScrapeNode.from_page(page)
        new_node2 = ScrapeNode.from_page(page)
        assert new_node1 is new_node2
        assert new_node1.__class__ == InsertableScrapeNode
        
    def test_no_visit_twice(self):
        # these games share the same lineups
        test_env.clean_db()
        games = [
            "WAS201710120.shtml",
            "CHN201710110.shtml"
        ]
        for game, expected_scrape_num in zip(games, [39, 1]):
            link = BBRefLink("WAS201710120.shtml")
            page = Page.from_link(link)
            node = ScrapeNode.from_page(page)
            assert node.scrape() == expected_scrape_num

PARSE_URLS: List[str] = [
    "https://www.baseball-reference.com/boxes/OAK/OAK201903200.shtml",
    "https://www.baseball-reference.com/boxes/HOU/HOU201710290.shtml",
    "https://www.baseball-reference.com/boxes/PHI/PHI198010080.shtml",
    "https://www.baseball-reference.com/boxes/ATL/ATL200706260.shtml",
    "https://www.baseball-reference.com/boxes/OAK/OAK201203280.shtml",
    "https://www.baseball-reference.com/boxes/BAL/BAL200705070.shtml",
    "https://www.baseball-reference.com/boxes/SEA/SEA199105260.shtml",
    "https://www.baseball-reference.com/boxes/SEA/SEA201903290.shtml",
    "https://www.baseball-reference.com/players/j/jimend'01.shtml",
    "https://www.baseball-reference.com/players/s/sabatc.01.shtml",
]

class TestParseable:
    
    @pytest.mark.parametrize("url", PARSE_URLS)
    def test_can_parse(self, url: str):
        test_env.clean_db()
        link = BBRefLink(url)
        page = Page.from_link(link)
        if isinstance(page, GamePage):
            test_env.insert_mock_players(page)
        ScrapeNode.from_page(page).scrape()

    def test_malformed_html(self):
        # the web handler will download the correct html, so need to copy
        # malformed html to cached file beforehand to test properly
        player_pages = os.path.join("tests", "scraping", "resources", "PlayerPage")
        copyfile(
                src = os.path.join(player_pages, "malformed_arod.shtml"),
                dst = os.path.join(player_pages, "rodrial01.shtml")
            )
        url = "https://www.baseball-reference.com/players/r/rodrial01.shtml"
        link = BBRefLink(url)
        page = Page.from_link(link)
