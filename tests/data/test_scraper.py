import pytest

from deepfield.data.bbref_pages import (BBRefLink, GamePage, PlayerPage,
                                        SchedulePage)
from deepfield.data.scraper import PageFactory, HtmlCache
import tests.data.test_utils

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
