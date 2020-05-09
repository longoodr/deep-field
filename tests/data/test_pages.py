from pathlib import Path

import pytest

from deepfield.data.dependencies import IgnoreDependencies
from deepfield.data.pages import SchedulePage


class TestSchedulePage():
    
    @classmethod
    def setup_method(cls):
        base_path = Path(__file__).parent
        file_path = (base_path / "resources/2016schedule.html").resolve()
        with open(file_path, "r", encoding="utf-8") as sched_file:
            html = sched_file.read()
            sched = SchedulePage(html, IgnoreDependencies())
            cls.page_urls = sched.get_referenced_page_urls()
            cls.models = sched._get_models_to_add()
            
    def test_urls_on_page(self):
        base_url = "https://www.baseball-reference.com"
        on_list_games = [
            "/boxes/KCA/KCA201604030.shtml",
            "/boxes/ANA/ANA201604040.shtml",
            "/boxes/TBA/TBA201604040.shtml",
        ]
        on_list = [base_url + g for g in on_list_games]
        for url in on_list:
            assert url in self.page_urls
        not_on_list = [
            "/leagues/MLB/2016-standard-batting.shtml",
            "/leagues/MLB/2016-schedule.shtml",
            "/boxes/BOS/BOS201708270.shtml"
        ]
        not_on_list = [base_url + suffix for suffix in not_on_list]
        for url in not_on_list:
            assert url not in self.page_urls
            
    def test_no_models(self):
        assert len(self.models) == 0
