from datetime import date, time
from pathlib import Path

import pytest
from peewee import SqliteDatabase

from deepfield.data.dbmodels import Game, Play, Player, Team, Venue
from deepfield.data.dependencies import IgnoreDependencies
from deepfield.data.enums import FieldType, TimeOfDay
from deepfield.data.pages import GamePage, SchedulePage

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
    
    @classmethod
    def setup_method(cls):
        base_path = Path(__file__).parent
        file_path = (get_res_path(cls.name)).resolve()
        with open(file_path, "r", encoding="utf-8") as page_file:
            html = page_file.read()
            page = cls.page_type(html, IgnoreDependencies())
            cls.page_urls = page.get_referenced_page_urls()
            page._run_queries()

class TestSchedulePage(TestPage):
    
    name = "2016schedule.html"
    page_type = SchedulePage
    
    def test_urls(self):
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

class TestGamePage(TestPage):
    
    name = "WAS201710120.shtml"
    page_type = GamePage

    def test_urls(self):
        pass

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
