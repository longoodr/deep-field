import pytest

from deepfield.data.bbref_pages import (BBRefLink, GamePage, PlayerPage,
                                        SchedulePage)
from deepfield.data.scraper import BBRefPageFactory
from tests.data.test_utils import get_res_path


class TestBBRefPageFactory:
    
    def test_page_types(self):
        for url, page_type in [
            ("https://www.baseball-reference.com/boxes/WAS/WAS201710120.shtml"   , GamePage),
            ("https://www.baseball-reference.com/leagues/MLB/2016-schedule.shtml", SchedulePage),
            ("https://www.baseball-reference.com/players/v/vendipa01.shtml", PlayerPage)
        ]:
            link = BBRefLink(url)
            assert type(BBRefPageFactory().create_page_from_link(link)) == page_type
