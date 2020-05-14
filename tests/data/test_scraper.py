import pytest

import tests.data.test_utils as test_utils
from deepfield.data.bbref_pages import (BBRefLink, GamePage, PlayerPage,
                                        SchedulePage)
from deepfield.data.scraping import (HtmlCache, InsertableScrapeNode,
                                    PageFactory, ScrapeNode)

RES_URLS = [
    "https://www.baseball-reference.com/boxes/WAS/WAS201710120.shtml",
    "https://www.baseball-reference.com/leagues/MLB/2016-schedule.shtml",
    "https://www.baseball-reference.com/players/v/vendipa01.shtml"
]

class TestBBRefPageFactory:
    
    def test_page_types(self):
        for url, page_type in zip(RES_URLS, [GamePage, SchedulePage, PlayerPage]):
            link = BBRefLink(url)
            assert type(PageFactory.create_page_from_link(link)) == page_type

class TestCache:
    
    def test_singleton(self):
        c1 = HtmlCache.get()
        c2 = HtmlCache.get()
        assert c1 is c2
    
    def test_find_html_in_cache(self):
        cache = HtmlCache.get()
        for url in RES_URLS:
            assert cache.find_html(BBRefLink(url)) is not None
            
    def test_find_html_not_in_cache(self):
        cache = HtmlCache.get()
        for url in [
            "ANA199742069.shtml",
            "1997-schedule.shtml",
            "burdege01.shtml"
        ]:
            assert cache.find_html(BBRefLink(url)) is None

class TestScrapeNode:
    
    def test_from_page(self):
        link = BBRefLink("WAS201710120.shtml")
        page = PageFactory.create_page_from_link(link)
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
            page = PageFactory.create_page_from_link(link)
            #test_utils.insert_mock_players(page)
            node = ScrapeNode.from_page(page)
            assert node.scrape() == expected_scrape_num