import re
from abc import ABC, abstractmethod
from datetime import date, datetime, time
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, Type

import requests
from bs4 import BeautifulSoup, Comment
from peewee import Query

from deepfield.data.dbmodels import (DeepFieldModel, Game, GamePlayer, Play,
                                     Player, Team, Venue, db)
from deepfield.data.enums import FieldType, Handedness, OnBase, TimeOfDay


class Link(ABC):
    """A page located at a URL that can determine if itself already exists in 
    the database or not.
    """
    
    def __init__(self, url: str):
        self._url = url
    
    @abstractmethod
    def exists_in_db(self) -> bool:
        """Returns whether this page already exists in the database."""
        pass
    
    def __str__(self):
        return self._url

class Page(ABC):
    """A collection of data located on an HTML page that references other pages
    via links.
    """
        
    def __init__(self, html: str):
        self._soup = BeautifulSoup(html, "lxml")
    
    @abstractmethod
    def get_links(self) -> Iterable[Link]:
        """Enumerates all referenced links on this page."""
        pass
    
class InsertablePage(Page):
    """A page containing data that can be inserted into the database. All
    referenced links are treated as dependencies of this page.
    """
    
    def update_db(self) -> None:
        """Inserts all models on this page into the database. This method
        requires all dependent pages to already exist in the database. If the
        page already exists in the database, this won't do anything.
        """
        if self._exists_in_db():
            return
        for link in self.get_links():
            if not link.exists_in_db():
                raise ValueError(f"Dependency for {link} not resolved")
        self._run_queries()
        
    @abstractmethod
    def _run_queries(self) -> None:
        """Runs all queries that need to be executed to properly insert this
        page into the database.
        """
        pass
    
    @abstractmethod
    def _exists_in_db(self) -> bool:
        """Returns whether this page already exists in the database."""
        pass

class BBRefPage(Page):
    """A page from baseball-reference.com."""
    
    def __init__(self, html: str):
        super().__init__(html)
        self.base_url = "https://www.baseball-reference.com"
        self.url = self._soup.find("link", rel="canonical")["href"]
    
class BBRefLink(Link):
    """A link from baseball-reference.com. These links all follow a similar
    format, where the last component of the URL is the name_id for the
    corresponding record in the database: "/.../.../name_id.ext"
    """
    
    def __init__(self, url: str, link_model: Type[DeepFieldModel]):
        self._url = url
        self._link_model = link_model
        self.name_id = self._get_name_id()
        
    def exists_in_db(self) -> bool:
        expr = self._link_model.name_id == self.name_id
        record = self._link_model.get_or_none(expr)
        return record is not None
    
    def _get_name_id(self) -> str:
        return self._url.split("/")[-1].split(".")[0]
    
class BBRefInsertablePage(BBRefPage, InsertablePage):
    
    def __init__(self, html: str, model: Type[DeepFieldModel]):
        super().__init__(html)
        self.base_url = "https://www.baseball-reference.com"
        url = self._soup.find("link", rel="canonical")["href"]
        self._link = BBRefLink(url, model)
        
    def _exists_in_db(self):
        return self._link.exists_in_db()

class SchedulePage(BBRefPage):
    """A page containing a set of URLs corresponding to game pages."""
    
    def get_links(self) -> Iterable[Link]:
        games = self._soup.find_all("p", {"class": "game"})
        for game in games:
            suffix = game.em.a["href"]
            url = self.base_url + suffix
            yield BBRefLink(url, Game)

class PlayerPage(BBRefInsertablePage):
    """A page containing info on a given player."""
    
    def __init__(self, html: str):
        super().__init__(html, Player)
        self._player_info = self._soup.find("div", {"itemtype": "https://schema.org/Person"})
    
    def get_links(self) -> Iterable[Link]:
        """PlayerPages don't depend on anything else."""
        return []
    
    def _run_queries(self) -> None:
        fields = self._get_handedness()
        fields["name"] = self._player_info.h1.text
        fields["name_id"] = self._link.name_id
        with db.atomic():
            Player.create(**fields)
    
    def _get_player_name(self) -> str:
        return self._player_info.h1.text
    
    _HANDEDNESS_MATCHER = re.compile(r"(?:Bats:|Throws:) (\w+)")
    
    def _get_handedness(self) -> Dict[str, Any]: # Bats, Throws
        handedness_p = self._player_info.find_all("p", limit=2)[-1]
        hands_text = re.findall(self._HANDEDNESS_MATCHER, handedness_p.text)
        hands: Dict[str, int] = {}
        hands["bats"]   = Handedness[hands_text[0].upper()].value
        hands["throws"] = Handedness[hands_text[1].upper()].value
        return hands

class GamePage(BBRefInsertablePage):
    """A page corresponding to the play-by-play info for a game, along with
    relevant info relating to the play-by-play data.
    """
    
    def __init__(self, html: str):
        super().__init__(html, Game)
        self._player_tables = _PlayerTables(self._soup)
        
    def _run_queries(self) -> None:
        if not hasattr(self, "_query_runner"):
            self._query_runner = _GamePageQueryRunner(self._soup, self._player_tables, self._link.name_id)
        self._query_runner.run_queries()
        
    def get_links(self) -> Iterable[Link]:
        """For a GamePage, the referenced links are the players' pages."""
        for suffix in self._player_tables.get_page_suffixes():
            url = self.base_url + suffix
            yield BBRefLink(url, Player)
            
    def _is_already_inserted(self) -> bool:
        game_record = Game.get_or_none(Game.name_id == self._link.name_id)
        return game_record is not None
    
    """There are a few edge cases for name lookups, since canonical player
    names and the names presented in play rows vary slightly. Players known
    with middle initials and/or with Jr./Sr. title may or may not be
    represented in play rows with these name elements. This allows names to be
    standardized across these different presentations.
    """
    _NAME_TITLE = re.compile(r" [J|S]r\.")
    _MIDDLE_INITIAL = re.compile(r" \w\.")

    @classmethod
    def _get_stripped_name(cls, name: str) -> str:
        name_wo_mid = re.sub(cls._MIDDLE_INITIAL, "", name)
        fully_stripped = re.sub(cls._NAME_TITLE, "", name_wo_mid)
        return fully_stripped
    
class _PlaceholderTable(BeautifulSoup):
    """Certain tables' contents are contained within comments, and are
    marked by divs with a class of placeholder preceding the comment of
    interest. Therefore, they should be instantiated by their placeholders.
    """
    
    def __init__(self, ph_div):
        # Note the SECOND sibling is the comment of interest because there is
        # an intermediate \n.
        table_contents = ph_div.next_sibling.next_sibling
        super().__init__(table_contents, "lxml")
        
class _PlayerTables:
    """Manages access to the tables of away and home players for the given
    game.
    """
    def __init__(self, soup):
        # player tables are marked by first 2 placeholders on page
        ptable_placeholders = list(soup.find_all("div", {"class": "placeholder"}, limit=2))
        self.away = _PlayerTable(ptable_placeholders[0])
        self.home = _PlayerTable(ptable_placeholders[1])
    
    def get_page_suffixes(self) -> Iterable[str]:
        for suffix in self.away.get_page_suffixes():
            yield suffix
        for suffix in self.home.get_page_suffixes():
            yield suffix
        
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
    
class _PlayerTable(_PlaceholderTable):
    """Manages access to a table of players."""
    
    _PLAYER_TAG_ATTR_FILTER = {
        "data-stat": "player",
        "scope": "row"
    }
            
    def get_page_suffixes(self) -> Iterable[str]:
        for row in self._get_rows():
            yield self._get_page_suffix(row)
    
    def get_name_ids(self) -> Iterable[str]:
        if not hasattr(self, "__name_ids"):
            self.__name_ids = [self._get_name_id(row) for row in self._get_rows()]
        return self.__name_ids
    
    def get_name_to_name_ids(self) -> Dict[str, str]:
        if not hasattr(self, "__name_to_name_ids"):
            self.__name_to_name_ids = {self._get_player_name(row): self._get_name_id(row) for row in self._get_rows()}
        return self.__name_to_name_ids
    
    def get_name_to_db_ids(self) -> Dict[str, int]:
        if not hasattr(self, "__name_to_db_ids"):
            name_ids = set(self.get_name_ids())
            name_ids_to_name = {nid: name for name, nid
                                in self.get_name_to_name_ids().items()}
            db_players = Player.select(Player.id, Player.name_id)\
                .where(Player.name_id.in_(name_ids))
            name_ids_to_db_ids = {p.name_id: p.id for p in db_players}
            self.__name_to_db_ids = {name_ids_to_name[nid]: name_ids_to_db_ids[nid]
                                    for nid in name_ids}
        return self.__name_to_db_ids
    
    def _get_rows(self):
        if not hasattr(self, "__rows"):
            self.__rows = self.find_all(
                self._player_tag_filter,
                attrs=self._PLAYER_TAG_ATTR_FILTER
                )
        return self.__rows
    
    @staticmethod
    def _get_player_name(row) -> str:
        canonical_name = row.a.text.replace(u"\xa0", u" ")
        return GamePage._get_stripped_name(canonical_name)
    
    @staticmethod
    def _get_name_id(row) -> str:
        page_suffix = _PlayerTable._get_page_suffix(row)
        return BBRefLink(page_suffix, Player).name_id
    
    @staticmethod
    def _get_page_suffix(row) -> str:
        return row.a["href"] # /players/s/smithjo01.shtml
                
    @staticmethod 
    def _player_tag_filter(tag) -> bool:
        return tag.name == "th" and len(tag.attrs) == 5

class _GamePageQueryRunner:
    """Handles execution of queries for data contained on a GamePage."""
    
    def __init__(self, soup, player_tables: _PlayerTables, game_name: str):
        self._soup = soup
        self._scorebox = self._soup.find("div", {"class": "scorebox"})
        self._scorebox_meta = self._scorebox.find("div", {"class": "scorebox_meta"})
        self._team_adder = _TeamQueryRunner(self._scorebox)
        self._venue_adder = _VenueQueryRunner(self._scorebox_meta)
        self._game_adder = _GameQueryRunner(self._soup, self._scorebox_meta, game_name)
        self._game_player_adder = _GamePlayerQueryRunner(player_tables)
        self._pbp_adder = _PlayQueryRunner(self._soup, player_tables)
        
    def run_queries(self) -> None:
        with db.atomic():
            teams = self._team_adder.add_teams()
            venue = self._venue_adder.add_venue()
            game = self._game_adder.add_game(teams, venue)
            self._game_player_adder.add_game_players(game)
            self._pbp_adder.add_plays(game)
        
class _TeamQueryRunner:
    
    def __init__(self, scorebox):
        self._scorebox = scorebox

    def add_teams(self) -> List[Team]:
        teams = []
        info = self._get_team_info()
        for name, abbreviation in info:
            team, _ = Team.get_or_create(name=name, abbreviation=abbreviation)
            teams.append(team)
        return teams
    
    def _get_team_info(self) -> Iterable[Tuple[str, str]]:
        """Returns 2 elements, which are tuples of the name and
        abbreviation for away, home teams respectively.
        """
        team_divs = self._scorebox.find_all("div", recursive=False, limit=2)
        for td in team_divs:
            yield self._get_team_div_info(td)
    
    @staticmethod
    def _get_team_div_info(td) -> Tuple[str, str]:
        team_info = td.div.strong.a
        suffix = team_info["href"] # /teams/abbreviation/year.html
        abbreviation = suffix.split("/")[2]
        name = str(team_info.string)
        return name, abbreviation
    
class _VenueQueryRunner:
    
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
    
class _GameQueryRunner:
    
    def __init__(self, soup, scorebox_meta, game_name: str):
        self._scorebox_meta = scorebox_meta
        self._game_name = game_name

    def add_game(self, teams: List[Team], venue: Venue) -> Game:
        fields = {
            "name_id"         : self._game_name,
            "local_start_time": self._get_local_start_time(),
            "time_of_day"     : self._enum_to_int(self._get_time_of_day()),
            "field_type"      : self._enum_to_int(self._get_field_type()),
            "date"            : self._get_date(),
            "venue_id"        : venue.id,
            "away_team_id"    : teams[0].id,
            "home_team_id"    : teams[1].id,
        }
        game, _ = Game.get_or_create(**fields)
        return game
        
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

class _PlayQueryRunner:
    
    def __init__(self, soup, player_tables: _PlayerTables):
        self._soup = soup
        self._pbp_table = self._get_pbp_table()
        self._transformer = _PlayDataTransformer(player_tables)
            
    def add_plays(self, game: Game) -> None:
        Play.insert_many(self._get_play_data(game)).execute()
        
    def _get_play_data(self, game: Game) -> Iterable[Dict[str, Any]]:
        for play_num, play_row in enumerate(self._get_play_rows()):
            raw_play_data = self._transformer.extract_raw_play_data(play_row)
            play_data = self._transformer.transform_raw_play_data(raw_play_data)
            play_data["game_id"] = game.id
            play_data["play_num"] = play_num
            yield play_data
        
    def _get_pbp_table(self) -> _PlaceholderTable:
        # pbp table placeholder is the 7th on page
        placeholders = self._soup.find_all("div", {"class": "placeholder"}, limit=7)
        ph = placeholders[-1]
        return _PlaceholderTable(ph)
    
    def _get_play_rows(self):
        return self._pbp_table.find_all(
            "tr",
            id=lambda id: id and id.startswith("event_")
            )
        
class _PlayDataTransformer:
    
    PBP_TO_DB_STATS: Dict[str, Tuple[str, Callable]]
    PLAYERS: Dict[str, Tuple[str, Callable]]
    PBP_STATS: Set[str]
    INNING_CHAR_OFFSET: Dict[str, int]
    INNING_AND_PLAYER_TO_SIDE: Dict[Tuple[str, str], str]
    
    def __init__(self, player_tables: _PlayerTables):
        self._init_lookups()
        self._player_maps = {
            "home": player_tables.home.get_name_to_db_ids(),
            "away": player_tables.away.get_name_to_db_ids(),
        }

    @classmethod
    def _init_lookups(cls):
        """Initializes dicts to lookup database stat names and
        transformation functions to translate page data to database format.
        This is a class method so it is only done once, as this would be a
        bit expensive to do for every page.
        """
        if hasattr(cls, "PBP_TO_DB_STATS"):
            return
        # these functions can translate to db data with only raw data as input
        cls.PBP_TO_DB_STATS = {
            "inning":               ("inning_half"  , cls._inning_to_inning_half),
            "pitches_pbp":          ("pitch_ct"     , cls._strip),
            "play_desc":            ("desc"         , cls._no_transformation_needed),
            "runners_on_bases_pbp": ("start_on_base", cls._runners_to_on_base),
            "outs":                 ("start_outs"   , cls._convert_to_int),
        }
        # these functions require knowledge of inning half to determine if home or away player
        cls.PLAYERS = {
            "batter":               ("batter_id"    , cls._batter_to_id),
            "pitcher":              ("pitcher_id"   , cls._pitcher_to_id),
        }
        cls.INNING_CHAR_OFFSET = {
            "t": 0,
            "b": 1
        }
        # home team gets to bat in second half of inning (b)
        cls.INNING_AND_PLAYER_TO_SIDE = {
            ("t", "batter") : "away",
            ("b", "batter") : "home",
            ("t", "pitcher"): "home",
            ("b", "pitcher"): "away",
        }
        cls.PBP_STATS = set(cls.PBP_TO_DB_STATS.keys()).union(set(cls.PLAYERS.keys()))
        
    def extract_raw_play_data(self, play_row) -> Dict[str, str]:
        raw_play_data: Dict[str, str] = {}
        for play_data_pt in play_row.find_all():
            data_stat = str(play_data_pt.get("data-stat"))
            if data_stat in self.PBP_STATS:
                raw_play_data[data_stat] = play_data_pt.text.replace(u"\xa0", u" ")
        return raw_play_data
    
    def transform_raw_play_data(self, raw_play_data: Dict[str, str]) -> Dict[str, Any]:
        transformed_stats = self._transform_stats(raw_play_data)
        self._insert_player_ids(raw_play_data, into_dict=transformed_stats)
        return transformed_stats
    
    def _transform_stats(self, raw_play_data: Dict[str, str]) -> Dict[str, str]:
        new_data: Dict[str, str] = {}
        for pbp_statname, (db_statname, transform_func) in self.PBP_TO_DB_STATS.items():
            new_data[db_statname] = transform_func(self, raw_play_data[pbp_statname])
        return new_data
    
    def _insert_player_ids(self, raw_play_data: Dict[str, str], into_dict: Dict[str, str]) -> Dict[str, str]:
        inning_half_char = raw_play_data["inning"][0]
        for player_type, (player_type_id, player_lookup_func) in self.PLAYERS.items():
            player_name = raw_play_data[player_type]
            into_dict[player_type_id] = player_lookup_func(self, player_name, inning_half_char)
        return into_dict
    
    def _inning_to_inning_half(self, inning: str) -> int:
        #[t|b][0-9]+ (t1, b2, t11, etc)
        inning_num = int(inning[1:])
        inning_half_char = inning[0]
        # 0-indexed (t1 -> 0; b1 -> 1; b2 -> 2 etc)
        return 2 * (inning_num - 1) + self.INNING_CHAR_OFFSET[inning_half_char]
    
    def _runners_to_on_base(self, runners: str) -> int:
        #[-|1][-|2][-|3] where - means nobody on base (---, 1-3, 12-, etc)
        on_base = 0
        for base, on_base_flag in zip(runners, [OnBase.FIRST, OnBase.SECOND, OnBase.THIRD]):
            if not base == "-":
                on_base += on_base_flag.value
        return on_base
    
    def _batter_to_id(self, batter_name: str, inning_half_char: str) -> str:
        return self._player_to_id(batter_name, inning_half_char, "batter")
    
    def _pitcher_to_id(self, pitcher_name: str, inning_half_char: str) -> str:
        return self._player_to_id(pitcher_name, inning_half_char, "pitcher")
    
    def _player_to_id(self, player_name: str, inning_half_char: str, player_type: str) -> str:
        side = self.INNING_AND_PLAYER_TO_SIDE[(inning_half_char, player_type)]
        pmap = self._player_maps[side]
        try:
            # first try unedited name, since there's some overhead w/ stripping
            return pmap[player_name]
        except KeyError:
            stripped_name = GamePage._get_stripped_name(player_name)
            return pmap[stripped_name]
        
        # if all attempts fail, there's a new edge case that needs to be
        # considered
        raise KeyError(player_name)
        
    def _strip(self, stat: str) -> str:
        return stat.strip()
    
    def _no_transformation_needed(self, stat: str) -> str:
        return stat
    
    def _convert_to_int(self, stat: str) -> int:
        return int(stat)

class _GamePlayerQueryRunner:
    
    def __init__(self, player_tables: _PlayerTables):
        name_ids =  set(player_tables.home.get_name_ids())
        name_ids.update(player_tables.away.get_name_ids())
        self._name_ids = name_ids
        
    def add_game_players(self, game: Game) -> None:
        GamePlayer.insert_many(
            self._get_rows(game),
            fields=[GamePlayer.game_id, GamePlayer.player_id]
            ).execute()

    def _get_rows(self, game: Game) -> Iterable[Tuple[int, int]]:
        for pid in Player.select(Player.id).where(Player.name_id.in_(self._name_ids)):
            yield (game.id, pid.id)
