from datetime import date, time
from pathlib import Path
from typing import Iterable, Type

import pytest
from peewee import SqliteDatabase

from deepfield.data.dbmodels import Game, Play, Player, Team, Venue
from deepfield.data.dependencies import IgnoreDependencies
from deepfield.data.enums import FieldType, OnBase, TimeOfDay
from deepfield.data.pages import GamePage, Page, SchedulePage

test_db = SqliteDatabase(":memory:")
MODELS = [Game, Play, Player, Team, Venue]

def get_res_path(name: str) -> Path:
    base_path = Path(__file__).parent
    return (base_path / ("resources/" + name)).resolve()

def setup_module(module):
    test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
    test_db.connect()
    test_db.create_tables(MODELS)

def teardown_module(module):
    test_db.drop_tables(MODELS)
    test_db.close()

class TestPage:
            
    base_url = "https://www.baseball-reference.com"
    page_type: Type[Page]
    page_urls: Iterable[str]
    
    @classmethod
    def setup_method(cls):
        file_path = (get_res_path(cls.name)).resolve()
        with open(file_path, "r", encoding="utf-8") as page_file:
            html = page_file.read()
            page = cls.page_type(html, IgnoreDependencies())
            cls.page_urls = page.get_referenced_page_urls()
            page._run_queries()
       
    @classmethod
    def expand_urls(cls, suffixes: Iterable[str]) -> Iterable[str]:
        return [cls.base_url + s for s in suffixes]

    @classmethod
    def test_urls(cls, on_list_suffixes: Iterable[str], not_on_list_suffixes: Iterable[str]):
        for url in cls.expand_urls(on_list_suffixes):
            assert url in cls.page_urls
        for url in cls.expand_urls(not_on_list_suffixes):
            assert url not in cls.page_urls

class TestSchedulePage(TestPage):
    
    name = "2016schedule.html"
    page_type = SchedulePage
    
    def test_urls(self):
        on_list = [
            "/boxes/KCA/KCA201604030.shtml",
            "/boxes/ANA/ANA201604040.shtml",
            "/boxes/TBA/TBA201604040.shtml",
        ]
        not_on_list = [
            "/leagues/MLB/2016-standard-batting.shtml",
            "/leagues/MLB/2016-schedule.shtml",
            "/boxes/BOS/BOS201708270.shtml"
        ]
        super().test_urls(on_list, not_on_list)

class TestGamePage(TestPage):
    
    name = "WAS201710120.shtml"
    page_type = GamePage

    def test_urls(self):
        on_list = [
            "/players/j/jayjo02.shtml",
            "/players/t/turnetr01.shtml",
            "/players/h/hendrky01.shtml",
            "/players/g/gonzagi01.shtml",
            "/players/d/daviswa01.shtml"
        ]
        not_on_list = [
            "/boxes/CHN/CHN201710090.shtml",
        ]
        super().test_urls(on_list, not_on_list)

    def test_queries(self):
        venue = Venue.get(Venue.name == "Nationals Park")
        home = Team.get(Team.name == "Washington Nationals" and Team.abbreviation == "WSN")
        away = Team.get(Team.name == "Chicago Cubs" and Team.abbreviation == "CHC")
        Game.get(
                Game.name_id == "WAS201710120"
                and Game.local_start_time == time(20, 8)
                and Game.time_of_day == TimeOfDay.NIGHT.value
                and Game.field_type == FieldType.GRASS.value
                and Game.date == date(2017, 10, 12)
                and Game.venue_id == venue.id
                and Game.home_team_id == home.id
                and Game.away_team_id == away.id
            )
