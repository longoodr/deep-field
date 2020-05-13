from datetime import date, time
from pathlib import Path
from typing import Iterable, Type

import pytest
from peewee import SqliteDatabase

from deepfield.data.dbmodels import (Game, GamePlayer, Play, Player, Team,
                                     Venue, db)
from deepfield.data.dependencies import IgnoreDependencies
from deepfield.data.enums import FieldType, Handedness, OnBase, TimeOfDay
from deepfield.data.pages import GamePage, Page, SchedulePage

db.init(":memory:")
MODELS = (Game, GamePlayer, Play, Player, Team, Venue)

def get_res_path(name: str) -> Path:
    base_path = Path(__file__).parent
    return (base_path / ("resources/" + name)).resolve()

class TestPage:
            
    base_url = "https://www.baseball-reference.com"
    page: Page
    page_type: Type[Page]
    
    @classmethod
    def setup_method(cls):
        db.create_tables(MODELS)
        file_path = (get_res_path(cls.name)).resolve()
        with open(file_path, "r", encoding="utf-8") as page_file:
            html = page_file.read()
            cls.page = cls.page_type(html, IgnoreDependencies())
    
    @classmethod
    def teardown_method(cls):
        db.drop_tables(MODELS)
    
    @classmethod
    def expand_urls(cls, suffixes: Iterable[str]) -> Iterable[str]:
        return [cls.base_url + s for s in suffixes]

    @classmethod
    def test_urls(cls, on_list_suffixes: Iterable[str], not_on_list_suffixes: Iterable[str]):
        page_urls = set(cls.page.get_referenced_page_urls())
        for url in cls.expand_urls(on_list_suffixes):
            assert url in page_urls
        for url in cls.expand_urls(not_on_list_suffixes):
            assert url not in page_urls

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
        self._insert_mock_players()
        self.page._run_queries()
        venue = Venue.get(Venue.name == "Nationals Park")
        home = Team.get(Team.name == "Washington Nationals" and Team.abbreviation == "WSN")
        away = Team.get(Team.name == "Chicago Cubs" and Team.abbreviation == "CHC")
        game = Game.get(
                Game.name_id == "WAS201710120"
                and Game.local_start_time == time(20, 8)
                and Game.time_of_day == TimeOfDay.NIGHT.value
                and Game.field_type == FieldType.GRASS.value
                and Game.date == date(2017, 10, 12)
                and Game.venue_id == venue.id
                and Game.home_team_id == home.id
                and Game.away_team_id == away.id
            )
        play = Play.get(
                Play.game_id == game.id
                and Play.inning_half == 0
                and Play.start_outs == 0
                and Play.start_on_base == OnBase.EMPTY.value
                and Play.play_num == 0
                and Play.desc == "Double to RF (Line Drive)"
                and Play.pitch_ct == "2,(0-1) CX"
                and Play.batter_id == self._id_of_name_id("jayjo02")
                and Play.pitcher_id == self._id_of_name_id("gonzagi01")
            )
        Play.get(
                Play.game_id == game.id
                and Play.inning_half == 4
                and Play.start_outs == 1
                and Play.start_on_base == (OnBase.FIRST | OnBase.SECOND).value
                and Play.play_num == 28
                and Play.desc == "Walk; Bryant to 3B; Contreras to 2B"
                and Play.pitch_ct == "6,(3-2) CBFBBB"
                and Play.batter_id == self._id_of_name_id("almoral01")
                and Play.pitcher_id == self._id_of_name_id("gonzagi01")
            )
        num_game_players = len(GamePlayer.select().where(GamePlayer.game_id == game.id))
        num_players = len(Player.select())
        assert(num_game_players == num_players)
        
    def _insert_mock_players(self) -> None:
        ptables = self.page._player_tables
        with db.atomic():
            for table in ptables:
                pmap = table.get_name_to_name_ids()
                for name, name_id in pmap.items():
                    self._insert_mock_player(name, name_id)
    
    @staticmethod    
    def _insert_mock_player(name: str, name_id: str) -> None:
        fields = {
            "name": name,
            "name_id": name_id,
            "bats": Handedness.RIGHT.value,
            "throws": Handedness.RIGHT.value,
        }
        Player.create(**fields)

    @staticmethod
    def _id_of_name_id(name_id: str) -> int:
        return Player.get(Player.name_id == name_id).id
