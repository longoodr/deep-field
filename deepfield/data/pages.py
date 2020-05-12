from abc import ABC, abstractmethod
from datetime import date, datetime, time
from typing import Callable, Dict, Iterable, List, Set, Tuple

import requests
from bs4 import BeautifulSoup, Comment
from peewee import Query

from deepfield.data.dbmodels import Game, Team, Venue
from deepfield.data.dependencies import DependencyResolver
from deepfield.data.enums import FieldType, OnBase, TimeOfDay


class Page(ABC):
    """A collection of data located on an HTML page. A page may have
    dependencies on pages located at URLs. This induces a dependency DAG which
    can be traversed via DFS by a scraper. The page will refuse to insert its
    data unless all these dependencies are resolved by the given
    DependencyResolver.
    """
        
    def __init__(self, html: str, dep_res: DependencyResolver):
        self._soup = BeautifulSoup(html, "lxml")
        self._dep_res = dep_res
    
    def update_db(self) -> None:
        """Inserts all models on this page into the database. This method
        requires all dependent pages to already exist in the database.
        """
        for url in self.get_referenced_page_urls():
            if not self._dep_res.is_url_resolved(url):
                raise ValueError(f"Dependency for {url} not resolved")
        self._run_queries()
        
    @abstractmethod
    def _run_queries(self) -> None:
        """Enumerates all queries that need to be executed to properly insert
        this page into the database.
        """
        pass
    
    @abstractmethod
    def get_referenced_page_urls(self) -> Iterable[str]:
        """Enumerates all referenced URLs that models on this page depend on."""
        pass

class BBRefPage(Page):
    """A page from baseball-reference.com"""
    
    def __init__(self, html: str, dep_res: DependencyResolver):
        super().__init__(html, dep_res)
        self.base_url = "https://www.baseball-reference.com"

class SchedulePage(BBRefPage):
    """A page containing a set of URLs corresponding to game pages."""
    
    def _run_queries(self) -> None:
        return
    
    def get_referenced_page_urls(self) -> Iterable[str]:
        urls = []
        games = self._soup.find_all("p", {"class": "game"})
        for game in games:
            suffix = game.em.a["href"]
            urls.append(self.base_url + suffix)
        return urls

class GamePage(BBRefPage):
    """A page corresponding to the play-by-play info for a game, along with
    relevant info relating to the play-by-play data.
    """
    
    def __init__(self, html: str, dep_res: DependencyResolver):
        super().__init__(html, dep_res)
        self._player_tables = self.PlayerTables(self._soup)
        
    def _run_queries(self) -> None:
        if not hasattr(self, "_query_runner"):
            self._query_runner = self.QueryRunner(self._soup, self._player_tables)
        self._query_runner.run_queries()
        
    def get_referenced_page_urls(self) -> Iterable[str]:
        player_suffixes = []
        for table in self._player_tables:
            player_suffixes += table.get_suffixes()
        return [self.base_url + s for s in player_suffixes]
    
    @staticmethod
    def _get_table_from_placeholder(ph_div) -> BeautifulSoup:
        """Certain tables' contents are contained within comments, and are
        marked by divs with a class of placeholder preceding the comment of
        interest. This instantiates a soup object from a given placeholder
        marking the location of a table comment. Note the SECOND sibling is
        the comment of interest because there is an intermediate \\n.
        """
        table_contents = ph_div.next_sibling.next_sibling
        return BeautifulSoup(table_contents, "lxml")
        
    class PlayerTables:
        """Manages access to the tables of away and home players for the given
        game.
        """
        def __init__(self, soup):
            # player tables are marked by first 2 placeholders on page
            ptable_placeholders = list(soup.find_all("div", {"class": "placeholder"}, limit=2))
            self.away = GamePage.PlayerTable(ptable_placeholders[0])
            self.home = GamePage.PlayerTable(ptable_placeholders[1])
            
        def __iter__(self):
            self._tables = [self.away, self.home]
            self._cur = 0
            return self
        
        def __next__(self):
            if self._cur >= len(self._tables):
                raise StopIteration
            this_table = self._tables[self._cur]
            self._cur += 1
            return this_table
        
    class PlayerTable:
        """Manages access to a table of players."""
        
        _player_tag_attr_filter = {
            "data-stat": "player",
            "scope": "row"
        }
        
        def __init__(self, placeholder):
            self._table = GamePage._get_table_from_placeholder(placeholder)
                
        def get_suffixes(self) -> List[str]:
            return [row.a["href"] for row in self.get_rows()]
        
        def get_name_map(self) -> Dict[str, str]:
            return {row.a.text.replace(u"\xa0", u" "): row.a["href"] for row in self.get_rows()}
        
        def get_rows(self):
            return self._table.find_all(
                self._player_tag_filter,
                attrs=self._player_tag_attr_filter
                )
                    
        @staticmethod 
        def _player_tag_filter(tag) -> bool:
            return tag.name == "th" and len(tag.attrs) == 5
    
    class QueryRunner:
        """Handles execution of queries for data contained on a GamePage."""
        
        def __init__(self, soup, player_tables):
            self._soup = soup
            self._scorebox = self._soup.find("div", {"class": "scorebox"})
            self._scorebox_meta = self._scorebox.find("div", {"class": "scorebox_meta"})
            self._team_adder = GamePage.TeamQueryRunner(self._scorebox)
            self._venue_adder = GamePage.VenueQueryRunner(self._scorebox_meta)
            self._game_adder = GamePage.GameQueryRunner(self._soup, self._scorebox_meta)
            self._pbp_adder = GamePage.PlayQueryRunner(self._soup, player_tables)
            
        def run_queries(self) -> None:
            teams = self._team_adder.add_teams()
            venue = self._venue_adder.add_venue()
            game = self._game_adder.add_game(teams, venue)
            self._pbp_adder.add_plays(game)
            
    class TeamQueryRunner:
        
        def __init__(self, scorebox):
            self._scorebox = scorebox
    
        def add_teams(self) -> List[Team]:
            teams = []
            info = self._get_team_info()
            for name, abbreviation in info:
                team, _ = Team.get_or_create(name=name, abbreviation=abbreviation)
                teams.append(team)
            return teams
        
        def _get_team_info(self) -> List[Tuple[str, str]]:
            """Returns a 2 element list, which contains tuples of the name and
            abbreviation for away, home teams respectively
            """
            team_divs = self._scorebox.find_all("div", recursive=False, limit=2)
            info: List[Tuple[str, str]] = []
            for td in team_divs:
                team_info = td.div.strong.a
                suffix = team_info["href"] # /teams/abbreviation/year.html
                abbreviation = suffix.split("/")[2]
                name = str(team_info.string)
                info.append((name, abbreviation))
            return info
        
    class VenueQueryRunner:
        
        def __init__(self, scorebox_meta):
            self._scorebox_meta = scorebox_meta
            
        def add_venue(self) -> Venue:
            name = self._get_venue_name()
            venue, _ = Venue.get_or_create(name=name)
            return venue
            
        def _get_venue_name(self) -> str:
            venue_div = self._scorebox_meta.find(self._venue_div_filter)
            return venue_div.text.split(": ")[1] # "Venue: <venue name>"
        
        @staticmethod
        def _venue_div_filter(div) -> bool:
            return div.text.startswith("Venue: ")
        
    class GameQueryRunner:
        
        def __init__(self, soup, scorebox_meta):
            self._scorebox_meta = scorebox_meta
            page_url = soup.find("link", rel="canonical")["href"] # /.../.../name.shtml
            self._name = page_url.split("/")[-1].split(".")[0]
    
        def add_game(self, teams: List[Team], venue: Venue) -> Game:
            fields = {
                "name_id": self._name,
                "local_start_time": self._get_local_start_time(),
                "time_of_day": self._enum_to_int(self._get_time_of_day()),
                "field_type": self._enum_to_int(self._get_field_type()),
                "date": self._get_date(),
                "venue_id": venue.id,
                "away_team_id": teams[0].id,
                "home_team_id": teams[1].id,
            }
            game, _ = Game.get_or_create(**fields)
            
        @staticmethod
        def _enum_to_int(enum):
            if enum is None:
                return None
            return enum.value
            
        def _get_local_start_time(self) -> time:
            lst_div = self._scorebox_meta.find(self._lst_filter)
            # Start Time: %I:%M [a.m.|p.m.] Local
            lst_text = lst_div.text.split("Time: ")[-1] # "%I:%M [a.m.|p.m.] Local"
            lst_text = lst_text.replace(" Local", "") # "%I:%M [a.m.|p.m.]"
            lst_text = lst_text.replace(".", "").upper() # "%I:%M %p"
            dt = datetime.strptime(lst_text, "%I:%M %p")
            return dt.time()
        
        @staticmethod
        def _lst_filter(div) -> bool:
            return "Time: " in div.text
        
        def _get_time_of_day(self) -> TimeOfDay:
            tod_div = self._scorebox_meta.find(self._tod_filter)
            if tod_div is None:
                return None
            # "day/night game, ..."
            tod_text = tod_div.text.split()[0]
            return TimeOfDay[tod_text.upper()]
        
        @staticmethod
        def _tod_filter(div) -> bool:
            for tod in ["day", "night"]:
                if div.text.lower().startswith(tod):
                    return True
            return False
        
        def _get_field_type(self) -> FieldType:
            field_div = self._scorebox_meta.find(self._field_div_filter)
            if field_div is None:
                return None
            # "... on turf/grass"
            field_text = field_div.text.split()[-1]
            return FieldType[field_text.upper()]
            
        @staticmethod
        def _field_div_filter(div) -> bool:
            for field in ["turf", "grass"]:
                if div.text.endswith(field):
                    return True
            return False
        
        def _get_date(self) -> date:
            date_div = self._scorebox_meta.find(self._date_div_filter)
            dt = datetime.strptime(date_div.text, "%A, %B %d, %Y")
            return dt.date()
        
        @staticmethod
        def _date_div_filter(div) -> bool:
            weekday = div.text.split()[0]
            return weekday.endswith("day,")

    class PlayQueryRunner:
        
        PBP_TO_DB_STATS: Dict[str, Tuple[str, Callable]]
        PLAYERS: Set[str]
        PBP_STATS: Set[str]
        INNING_CHAR_OFFSET: Dict[str, int]
        
        def __init__(self, soup, player_tables):
            self._soup = soup
            self._pbp_table = self._get_pbp_table()
            self._home_map = player_tables.home.get_name_map()
            self._away_map = player_tables.away.get_name_map()
            self._init_class_vars()
            
        # FIXME this approach won't work, as player lookups require knowledge
        # of whether they're on the home or away team
        def _init_lookups(self):
            if hasattr(self, "PBP_TO_DB_STATS"):
                return
            self.PBP_TO_DB_STATS = {
                "inning":               ("inning_half"  , self._inning_to_inning_half),
                "pitches_pbp":          ("pitch_ct"     , lambda x: x),
                "play_desc":            ("desc"         , lambda x: x),
                "runners_on_bases_pbp": ("start_on_base", self._runners_to_on_base),
                "outs":                 ("start_outs"   , lambda x: int(x)),
                "batter":               ("batter_id"    , self._batter_to_id),
                "pitcher":              ("pitcher_id"   , self._pitcher_to_id),
            }
            self.PLAYERS = set([
                "batter",
                "pitcher",
                ])
            self.PBP_STATS = set(self.PBP_TO_DB_STATS.keys())
            self.INNING_CHAR_OFFSET = {
                "t": 0,
                "b": 1
            }
                
        def add_plays(self, game: Game) -> None:
            for play_row in self._get_play_rows():
                self._add_play(play_row)
            
        def _add_play(self, play_row) -> None:
            raw_play_data = self._extract_raw_play_data(play_row)
            new_data = self._transform_raw_play_data(raw_play_data)
            pass
            
        def _extract_raw_play_data(self, play_row) -> Dict[str, str]:
            raw_play_data: Dict[str, str] = {}
            for play_data_pt in play_row.find_all():
                data_stat = str(play_data_pt.get("data-stat"))
                if data_stat in self.PBP_STATS:
                    raw_play_data[data_stat] = play_data_pt.text.replace(u"\xa0", u" ")
            return raw_play_data
        
        def _transform_raw_play_data(self, raw_play_data) -> Dict[str, str]:
            new_data: Dict[str, str] = {}
            for pbp_statname, (db_statname, transform_func) in self.PBP_TO_DB_STATS.items():
                new_data[db_statname] = transform_func(raw_play_data[pbp_statname])
            return new_data
        
        @classmethod
        def _inning_to_inning_half(cls, inning: str) -> int:
            inning_num = int(inning[1:])
            inning_half_char = inning[0]
            return 2 * (inning_num - 1) + cls.INNING_CHAR_OFFSET[inning_half_char]
        
        @staticmethod
        def _runners_to_on_base(runners: str) -> int:
            on_base = 0
            for base, on_base_flag in zip(runners, [OnBase.FIRST, OnBase.SECOND, OnBase.THIRD]):
                if not base == "-":
                    on_base += on_base_flag.value
            return on_base
        
        def _batter_to_id(self, batter_name: str) -> str:
            pass
        
        def _pitcher_to_id(self, pitcher_name: str) -> str:
            pass
            
        def _get_pbp_table(self):
            # pbp table placeholder is the 7th on page
            placeholders = self._soup.find_all("div", {"class": "placeholder"}, limit=7)
            ph = placeholders[-1]
            return GamePage._get_table_from_placeholder(ph)
        
        def _get_play_rows(self):
            return self._pbp_table.find_all(
                "tr",
                id=lambda id: id and id.startswith("event_")
                )
