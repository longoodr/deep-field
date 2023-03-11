from datetime import date, time
from typing import Iterable, Tuple, Type

from pytest import raises

from deepfield.db.models import Game, Play, Player, Team, Venue
from deepfield.db.enums import FieldType, Handedness, OnBase, TimeOfDay
from deepfield.scraping.bbref_pages import (BBRefLink, BBRefPage, GamePage,
                                            PlayerPage, SchedulePage)
from deepfield.scraping.pages import HtmlCache, Page
from tests import utils

RES_URLS = [
    "https://www.baseball-reference.com/boxes/WAS/WAS201710120.shtml",
    "https://www.baseball-reference.com/leagues/MLB/2016-schedule.shtml",
    "https://www.baseball-reference.com/players/v/vendipa01.shtml"
]

def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.remove_db()

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

class TestPage:

    name: str
    page: BBRefPage
    page_type: Type[BBRefPage]

    @classmethod
    def setup_method(cls):
        utils.clear_db()
        html = HtmlCache.get().find_html(BBRefLink(cls.name))
        cls.page = cls.page_type(html)  # type: ignore

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
    page: PlayerPage

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

class AbstractTestGamePage(TestPage):

    page_type = GamePage
    page: GamePage

    @staticmethod
    def _id_of_name_id(name_id: str) -> int:
        return Player.get(Player.name_id == name_id).id

class TestGamePage(AbstractTestGamePage):

    name = "WAS201710120.shtml"

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
        utils.insert_mock_players(self.page)
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
        assert len(list(Play.select())) == 97

class TestGamePageNames(AbstractTestGamePage):

    player_type: str
    plays: Iterable[Tuple[int, str]] # play_num, name_id

    def _test_queries(self):
        utils.insert_mock_players(self.page)
        self.page.update_db()
        assert self.page._exists_in_db()
        for play_num, name_id in self.plays:
            Play.get(
                Play.play_num == play_num
                and getattr(Play, self.player_type + "_id")
            )


class TestGamePageSameNames(TestGamePageNames):

    name = "BAL200705070.shtml"
    player_type = "pitcher"
    plays = [
        ( 3, "hernaro01"),
        ( 4, "hernaro01"),
        ( 5, "hernaro01"),
        (66, "hernaro01"),
        (82, "carmofa01"),
        (83, "carmofa01"),
        (84, "carmofa01"),
    ]
    def test_queries(self):
        self._test_queries()

class TestGamePageFatherAndSon(TestGamePageNames):

    name = "SEA199105260.shtml"
    player_type = "batter"
    plays = [
        ( 9, "griffke01"),
        (26, "griffke01"),
        (48, "griffke01"),
        (82, "griffke02"),
        (83, "griffke02"),
        (84, "griffke01"),
    ]
    def test_queries(self):
        self._test_queries()

class TestPlayerTables(TestPage):

    name = "OAK201903200.shtml"
    page_type = GamePage
    page: GamePage

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
