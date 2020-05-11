from abc import ABC, abstractmethod
from datetime import date, time, datetime
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup, Comment
from peewee import Query

from deepfield.data.dbmodels import Game, Team, Venue
from deepfield.data.dependencies import DependencyResolver
from deepfield.data.enums import TimeOfDay, FieldType

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
        
    def _run_queries(self) -> None:
        if not hasattr(self, "_query_runner"):
            self._query_runner = self.QueryRunner(self._soup)
        self._query_runner.run_queries()
        
    def get_referenced_page_urls(self) -> Iterable[str]:
        if not hasattr(self, "_dep_extractor"):
            self._dep_extractor = self.DepExtractor(self._soup)
        player_suffixes = self._dep_extractor.get_player_page_suffixes()
        return [self.base_url + s for s in player_suffixes]
    
    class QueryRunner:
        """Handles execution of queries for data contained on a GamePage."""
        
        def __init__(self, soup):
            self._soup = soup
            self._scorebox = self._soup.find("div", {"class": "scorebox"})
            self._scorebox_meta = self._scorebox.find("div", {"class": "scorebox_meta"})
            self._team_adder = self.TeamQueryRunner(self._scorebox)
            self._venue_adder = self.VenueQueryRunner(self._scorebox_meta)
            self._game_adder = self.GameQueryRunner(self._soup, self._scorebox_meta)
            
        def run_queries(self) -> None:
            # TODO: should add the teams, venue, game, contained plays in that order
            teams = self._team_adder.add_teams()
            venue = self._venue_adder.add_venue()
            game = self._game_adder.add_game(teams, venue)
            
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
            
            def __init__(self, pbp_table):
                self._pbp_table = pbp_table
    class DepExtractor:
        """Handles retrieving the referenced page URLs (player pages) for a
        GamePage.
        """
            
        _player_tag_attr_filter = {
            "data-stat": "player",
            "scope": "row"
        }
        
        def __init__(self, soup):
            self._soup = soup
            self._parse_player_tables()
        
        def _parse_player_tables(self) -> None:
            """Info in player tables are stored in comments, so they need to be
            parsed into soup objects themselves. Each table is preceded by a div
            with a class of placeholder.
            """
            player_table_placeholders = self._soup.find_all("div", {"class": "placeholder"}, limit=2)
            
            # the second sibling is the comment of interest because there is an intermediate \n
            player_table_contents = [p.next_sibling.next_sibling for p in player_table_placeholders]
            self._player_tables = [BeautifulSoup(c, "lxml") for c in player_table_contents]
            
        def get_player_page_suffixes(self):
            suffixes = []
            for player_table in self._player_tables:
                for ptag in player_table.find_all(self._player_tag_filter,
                                                attrs=self._player_tag_attr_filter):
                    suffixes.append(ptag.a["href"])
            return suffixes
            
        @staticmethod 
        def _player_tag_filter(tag) -> bool:
            return tag.name == "th" and len(tag.attrs) == 5