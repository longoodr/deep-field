import pytest

import tests.data.test_utils as test_utils
from deepfield.data.bbref_pages import (BBRefLink, GamePage, PlayerPage,
                                        SchedulePage)
from deepfield.data.pages import HtmlCache, Page
from deepfield.data.scraping import InsertableScrapeNode, ScrapeNode

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
        test_utils.clean_db()
        games = [
            "WAS201710120.shtml",
            "CHN201710110.shtml"
        ]
        for game, expected_scrape_num in zip(games, [39, 1]):
            link = BBRefLink("WAS201710120.shtml")
            page = Page.from_link(link)
            #test_utils.insert_mock_players(page)
            node = ScrapeNode.from_page(page)
            assert node.scrape() == expected_scrape_num
