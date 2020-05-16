from datetime import date, time
from pathlib import Path
from typing import Iterable, Type

import pytest
from pytest import raises

import tests.data.test_env as test_env
from deepfield.data.bbref_pages import (BBRefLink, BBRefPage, GamePage,
                                        PlayerPage, SchedulePage)
from deepfield.data.dbmodels import (Game, Play, Player, Team,
                                     Venue, db)
from deepfield.data.enums import FieldType, Handedness, OnBase, TimeOfDay
from deepfield.data.pages import HtmlCache, Page

RES_URLS = [
    "https://www.baseball-reference.com/boxes/WAS/WAS201710120.shtml",
    "https://www.baseball-reference.com/leagues/MLB/2016-schedule.shtml",
    "https://www.baseball-reference.com/players/v/vendipa01.shtml"
]

class TestPageFromLink:
    
    def test_page_types(self):
        for url, page_type in zip(RES_URLS, [GamePage, SchedulePage, PlayerPage]):
            link = BBRefLink(url)
            assert type(Page.from_link(link)) == page_type

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

class TestPage:
            
    name: str
    page: BBRefPage
    page_type: Type[BBRefPage]
    
    @classmethod
    def setup_method(cls):
        test_env.clean_db()
        html = test_env.resources.find_html(BBRefLink(cls.name))
        cls.page = cls.page_type(html)

    @classmethod
    def test_urls(cls, on_list_suffixes: Iterable[str], not_on_list_suffixes: Iterable[str]):
        page_urls = set([str(link) for link in cls.page.get_links()])
        for url in cls._expand_urls(on_list_suffixes):
            assert url in page_urls
        for url in cls._expand_urls(not_on_list_suffixes):
            assert url not in page_urls
            
    @classmethod
    def _expand_urls(cls, suffixes: Iterable[str]) -> Iterable[str]:
        return [cls.page.BASE_URL + s for s in suffixes]

    def _test_hash_eq(self, other_name: str):
        link = BBRefLink(self.name)
        link2 = BBRefLink(self.name)
        p1 = Page.from_link(link)
        p2 = Page.from_link(link)
        assert hash(link) == hash(link2)
        assert link == link2
        assert hash(p1) == hash(p2)
        assert p1 == p2
        game_link = BBRefLink(other_name)
        p3 = Page.from_link(game_link)
        assert hash(link) != hash(game_link)
        assert link != game_link
        assert hash(p1) != hash(p3)
        assert p1 != p3

class TestSchedulePage(TestPage):
    
    name = "2016-schedule.shtml"
    page_type = SchedulePage
    
    def test_hash_eq(self):
        self._test_hash_eq(TestGamePage.name)
    
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

class TestPlayerPage(TestPage):
    
    name = "vendipa01.shtml"
    page_type = PlayerPage
    
    def test_hash_eq(self):
        self._test_hash_eq(TestGamePage.name)
    
    def test_queries(self):
        assert not self.page._exists_in_db()
        self.page.update_db()
        assert self.page._exists_in_db()
        Player.get(Player.name == "Pat Venditte"
                   and Player.name_id == "vendipa01"
                   and Player.bats == Handedness.LEFT.value
                   and Player.throws == Handedness.BOTH.value)

class TestGamePage(TestPage):
    
    name = "WAS201710120.shtml"
    page_type = GamePage

    def test_hash_eq(self):
        self._test_hash_eq(TestSchedulePage.name)

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
        with raises(ValueError):
            self.page.update_db()
        insert_mock_players(self.page)
        assert not self.page._exists_in_db()
        self.page.update_db()
        assert self.page._exists_in_db()
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
                and Play.batter_id == self.__id_of_name_id("jayjo02")
                and Play.pitcher_id == self.__id_of_name_id("gonzagi01")
            )
        Play.get(
                Play.game_id == game.id
                and Play.inning_half == 4
                and Play.start_outs == 1
                and Play.start_on_base == (OnBase.FIRST | OnBase.SECOND).value
                and Play.play_num == 28
                and Play.desc == "Walk; Bryant to 3B; Contreras to 2B"
                and Play.pitch_ct == "6,(3-2) CBFBBB"
                and Play.batter_id == self.__id_of_name_id("almoral01")
                and Play.pitcher_id == self.__id_of_name_id("gonzagi01")
            )

    @staticmethod
    def __id_of_name_id(name_id: str) -> int:
        return Player.get(Player.name_id == name_id).id

class TestPlayerTables(TestPage):
    
    name = "OAK201903200.shtml"
    page_type = GamePage
    
    def test_players(self):
        away = [
            "gordode01",
            "hanigmi01",
            "bruceja01",
            "strichu01"
        ]
        home = [
            "laurera01",
            "chapmma01",
            "piscost01",
            "trivilo01"
        ]
        for on_list, not_on_list, ptable in zip(
                [away, home],
                [home, away],
                [self.page._player_tables.away, self.page._player_tables.home]
            ):
            for p in on_list:
                assert p in ptable.get_name_ids()
            for p in not_on_list:
                assert p not in ptable.get_name_ids()
    

def insert_mock_players(page: GamePage) -> None:
    ptables = page._player_tables
    with db.atomic():
        for table in ptables:
            pmap = table.get_name_to_name_ids()
            for name, name_id in pmap.items():
                _insert_mock_player(name, name_id)

def _insert_mock_player(name: str, name_id: str) -> None:
    fields = {
        "name": name,
        "name_id": name_id,
        "bats": Handedness.RIGHT.value,
        "throws": Handedness.RIGHT.value,
    }
    if Player.get_or_none(Player.name_id == name_id) is None:
        Player.create(**fields)