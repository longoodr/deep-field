import re
from datetime import date, datetime, time
from typing import (Any, Callable, Dict, Iterable, List, Optional, Set, Tuple,
                    Type)

import requests
from bs4 import BeautifulSoup, Comment
from peewee import Query

from deepfield.data.dbmodels import (DeepFieldModel, Game, GamePlayer, Play,
                                     Player, Team, Venue, db)
from deepfield.data.enums import FieldType, Handedness, OnBase, TimeOfDay
from deepfield.data.pages import InsertablePage, Link, Page


class BBRefPage(Page):
    """A page from baseball-reference.com."""
    
    BASE_URL = "https://www.baseball-reference.com"
    
    def __init__(self, html: str):
        super().__init__(html)
        url = self._soup.find("link", rel="canonical")["href"]
        self._link = BBRefLink(url)
        
    def __hash__(self):
        return hash(self._link)
    
    def __eq__(self, other) -> bool:
        return (self.__class__ == other.__class__
                and self._link == other._link
            )
        
    def __str__(self) -> str:
        return str(self._link.name_id)
    
class BBRefLink(Link):
    """A link from baseball-reference.com. These links all follow a similar
    format, where the last component of the URL is the name_id for the
    corresponding record in the database: "/.../.../name_id.ext". Each link
    also knows the type of the Page that it points to.
    """
    
    def __init__(self, url: str):
        super().__init__(url)
        self._link_model = self.__get_link_model()
        
    def exists_in_db(self) -> bool:
        if self._link_model is None:
            raise TypeError("Model not defined for this link")
        expr = (self._link_model.name_id == self.name_id)
        record = self._link_model.get_or_none(expr)
        return record is not None
    
    __PLAYER_NAME_ID_MATCHER = re.compile(r"^\w+\d\d$")
    __GAME_NAME_ID_MATCHER   = re.compile(r"[A-Z]{3}\d{9}")
    
    def _get_page_type(self) -> Type[BBRefPage]:
        if re.fullmatch(self.__GAME_NAME_ID_MATCHER, self.name_id):
            return GamePage
        elif re.match(self.__PLAYER_NAME_ID_MATCHER, self.name_id):
            return PlayerPage
        elif "schedule" in self._url:
            return SchedulePage
        raise ValueError(f"Could not determine page type of {self}")
    
    __TYPE_TO_MODEL: Dict[str, Optional[Type[DeepFieldModel]]] = {
        "GamePage"    : Game,
        "PlayerPage"  : Player,
        "SchedulePage": None
    }
    
    def __get_link_model(self) -> Optional[Type[DeepFieldModel]]:
        return self.__TYPE_TO_MODEL[self.page_type.__name__]
    
class BBRefInsertablePage(BBRefPage, InsertablePage):
    
    def __init__(self, html: str, model: Type[DeepFieldModel]):
        super().__init__(html)
        
    def _exists_in_db(self):
        return self._link.exists_in_db()

class SchedulePage(BBRefPage):
    """A page containing a set of URLs corresponding to game pages."""
    
    def get_links(self) -> Iterable[Link]:
        games = self._soup.find_all("p", {"class": "game"})
        for game in games:
            suffix = game.em.a["href"]
            url = self.BASE_URL + suffix
            yield BBRefLink(url)

class PlayerPage(BBRefInsertablePage):
    """A page containing info on a given player."""
    
    def __init__(self, html: str):
        super().__init__(html, Player)
        self._player_info = self._soup.find("div", {"itemtype": "https://schema.org/Person"})
    
    def get_links(self) -> Iterable[Link]:
        """PlayerPages don't depend on anything else."""
        return []
    
    def _run_queries(self) -> None:
        fields = self.__get_handedness()
        fields["name"] = self._player_info.h1.text
        fields["name_id"] = self._link.name_id
        with db.atomic():
            Player.create(**fields)
    
    def __get_player_name(self) -> str:
        return self._player_info.h1.text
    
    __HANDEDNESS_MATCHER = re.compile(r"(?:Bats:|Throws:) (\w+)")
    
    def __get_handedness(self) -> Dict[str, Any]: # Bats, Throws
        handedness_p = self._player_info.find_all("p", limit=2)[-1]
        hands_text = re.findall(self.__HANDEDNESS_MATCHER, handedness_p.text)
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
        
    def get_links(self) -> Iterable[Link]:
        """For a GamePage, the referenced links are the players' pages."""
        for suffix in self._player_tables.get_page_suffixes():
            url = self.BASE_URL + suffix
            yield BBRefLink(url)
        
    def _run_queries(self) -> None:
        if not hasattr(self, "_query_runner"):
            self.__query_runner = _GamePageQueryRunner(self._soup, self._player_tables, self._link.name_id)
        self.__query_runner.run_queries()
    
class _NameStripper:
    """There are a few edge cases for name lookups, since canonical player
    names and the names presented in play rows vary slightly. Players known
    with middle initials and/or with Jr./Sr. title may or may not be
    represented in play rows with these name elements. This allows names to be
    standardized across these different presentations.
    """
    __NAME_TITLE = re.compile(r" [J|S]r\.")
    __MIDDLE_INITIAL = re.compile(r" \w\.")

    @classmethod
    def get_stripped_name(cls, name: str) -> str:
        name_wo_mid = re.sub(cls.__MIDDLE_INITIAL, "", name)
        fully_stripped = re.sub(cls.__NAME_TITLE, "", name_wo_mid)
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
        for table in self:
            for suffix in table.get_page_suffixes():
                yield suffix
        
    def __iter__(self):
        self.__tables = [self.away, self.home]
        self.__cur = 0
        return self
    
    def __next__(self):
        if self.__cur >= len(self.__tables):
            raise StopIteration
        this_table = self.__tables[self.__cur]
        self.__cur += 1
        return this_table
    
class _PlayerTable(_PlaceholderTable):
    """Manages access to a table of players."""
    
    __PLAYER_TAG_ATTR_FILTER = {
        "data-stat": "player",
        "scope": "row"
    }
            
    def get_page_suffixes(self) -> Iterable[str]:
        for row in self.__get_rows():
            yield self.__get_page_suffix(row)
    
    def get_name_ids(self) -> Iterable[str]:
        if not hasattr(self, "__name_ids"):
            self.__name_ids = [self.__get_name_id(row) for row in self.__get_rows()]
        return self.__name_ids
    
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
    
    def get_name_to_name_ids(self) -> Dict[str, str]:
        if not hasattr(self, "__name_to_name_ids"):
            self.__name_to_name_ids = {self.__get_player_name(row): self.__get_name_id(row) for row in self.__get_rows()}
        return self.__name_to_name_ids
    
    def __get_rows(self):
        if not hasattr(self, "__rows"):
            self.__rows = self.find_all(
                self._player_tag_filter,
                attrs=self.__PLAYER_TAG_ATTR_FILTER
                )
        return self.__rows
    
    @staticmethod
    def __get_player_name(row) -> str:
        canonical_name = row.a.text.replace(u"\xa0", u" ")
        return _NameStripper.get_stripped_name(canonical_name)
    
    @staticmethod
    def __get_name_id(row) -> str:
        page_suffix = _PlayerTable.__get_page_suffix(row)
        return BBRefLink(page_suffix).name_id
    
    @staticmethod
    def __get_page_suffix(row) -> str:
        return row.a["href"] # /players/s/smithjo01.shtml
                
    @staticmethod 
    def _player_tag_filter(tag) -> bool:
        return tag.name == "th" and len(tag.attrs) == 5

class _GamePageQueryRunner:
    """Handles execution of queries for data contained on a GamePage."""
    
    def __init__(self, soup, player_tables: _PlayerTables, game_name: str):
        self.__soup = soup
        self.__scorebox = self.__soup.find("div", {"class": "scorebox"})
        self.__scorebox_meta = self.__scorebox.find("div", {"class": "scorebox_meta"})
        self.__team_adder = _TeamQueryRunner(self.__scorebox)
        self.__venue_adder = _VenueQueryRunner(self.__scorebox_meta)
        self.__game_adder = _GameQueryRunner(self.__soup, self.__scorebox_meta, game_name)
        self.__game_player_adder = _GamePlayerQueryRunner(player_tables)
        self.__pbp_adder = _PlayQueryRunner(self.__soup, player_tables)
        
    def run_queries(self) -> None:
        with db.atomic():
            teams = self.__team_adder.add_teams()
            venue = self.__venue_adder.add_venue()
            game = self.__game_adder.add_game(teams, venue)
            self.__game_player_adder.add_game_players(game)
            self.__pbp_adder.add_plays(game)
        
class _TeamQueryRunner:
    
    def __init__(self, scorebox):
        self.__scorebox = scorebox

    def add_teams(self) -> List[Team]:
        teams = []
        info = self.__get_team_info()
        for name, abbreviation in info:
            team, _ = Team.get_or_create(name=name, abbreviation=abbreviation)
            teams.append(team)
        return teams
    
    def __get_team_info(self) -> Iterable[Tuple[str, str]]:
        """Returns 2 elements, which are tuples of the name and
        abbreviation for away, home teams respectively.
        """
        team_divs = self.__scorebox.find_all("div", recursive=False, limit=2)
        for td in team_divs:
            yield self.__get_team_div_info(td)
    
    @staticmethod
    def __get_team_div_info(td) -> Tuple[str, str]:
        team_info = td.div.strong.a
        suffix = team_info["href"] # /teams/abbreviation/year.html
        abbreviation = suffix.split("/")[2]
        name = str(team_info.string)
        return name, abbreviation
    
class _VenueQueryRunner:
    
    def __init__(self, scorebox_meta):
        self.__scorebox_meta = scorebox_meta
        
    def add_venue(self) -> Venue:
        name = self.__get_venue_name()
        venue, _ = Venue.get_or_create(name=name)
        return venue
        
    def __get_venue_name(self) -> str:
        venue_div = self.__scorebox_meta.find(self.__venue_div_filter)
        return venue_div.text.split(": ")[1] # "Venue: <venue name>"
    
    @staticmethod
    def __venue_div_filter(div) -> bool:
        return div.text.startswith("Venue: ")
    
class _GameQueryRunner:
    
    def __init__(self, soup, scorebox_meta, game_name: str):
        self.__scorebox_meta = scorebox_meta
        self.__game_name = game_name

    def add_game(self, teams: List[Team], venue: Venue) -> Game:
        fields = {
            "name_id"         : self.__game_name,
            "local_start_time": self.__get_local_start_time(),
            "time_of_day"     : self.__enum_to_int(self.__get_time_of_day()),
            "field_type"      : self.__enum_to_int(self.__get_field_type()),
            "date"            : self.__get_date(),
            "venue_id"        : venue.id,
            "away_team_id"    : teams[0].id,
            "home_team_id"    : teams[1].id,
        }
        game, _ = Game.get_or_create(**fields)
        return game
        
    @staticmethod
    def __enum_to_int(enum):
        if enum is None:
            return None
        return enum.value
        
    def __get_local_start_time(self) -> time:
        lst_div = self.__scorebox_meta.find(self.__lst_filter)
        # Start Time: %I:%M [a.m.|p.m.] Local
        lst_text = lst_div.text.split("Time: ")[-1] # "%I:%M [a.m.|p.m.] Local"
        lst_text = lst_text.replace(" Local", "") # "%I:%M [a.m.|p.m.]"
        lst_text = lst_text.replace(".", "").upper() # "%I:%M %p"
        dt = datetime.strptime(lst_text, "%I:%M %p")
        return dt.time()
    
    @staticmethod
    def __lst_filter(div) -> bool:
        return "Time: " in div.text
    
    def __get_time_of_day(self) -> Optional[TimeOfDay]:
        tod_div = self.__scorebox_meta.find(self.__tod_filter)
        if tod_div is None:
            return None
        # "day/night game, ..."
        tod_text = tod_div.text.split()[0]
        return TimeOfDay[tod_text.upper()]
    
    @staticmethod
    def __tod_filter(div) -> bool:
        for tod in ["day", "night"]:
            if div.text.lower().startswith(tod):
                return True
        return False
    
    def __get_field_type(self) -> Optional[FieldType]:
        field_div = self.__scorebox_meta.find(self.__field_div_filter)
        if field_div is None:
            return None
        # "... on turf/grass"
        field_text = field_div.text.split()[-1]
        return FieldType[field_text.upper()]
        
    @staticmethod
    def __field_div_filter(div) -> bool:
        for field in ["turf", "grass"]:
            if div.text.endswith(field):
                return True
        return False
    
    def __get_date(self) -> date:
        date_div = self.__scorebox_meta.find(self.__date_div_filter)
        dt = datetime.strptime(date_div.text, "%A, %B %d, %Y")
        return dt.date()
    
    @staticmethod
    def __date_div_filter(div) -> bool:
        weekday = div.text.split()[0]
        return weekday.endswith("day,")

class _PlayQueryRunner:
    
    def __init__(self, soup, player_tables: _PlayerTables):
        self.__soup = soup
        self.__pbp_table = self.__get_pbp_table()
        self.__transformer = _PlayDataTransformer(player_tables)
            
    def add_plays(self, game: Game) -> None:
        Play.insert_many(self.__get_play_data(game)).execute()
        
    def __get_play_data(self, game: Game) -> Iterable[Dict[str, Any]]:
        for play_num, play_row in enumerate(self.__get_play_rows()):
            raw_play_data = self.__transformer.extract_raw_play_data(play_row)
            play_data = self.__transformer.transform_raw_play_data(raw_play_data)
            play_data["game_id"] = game.id
            play_data["play_num"] = play_num
            yield play_data
        
    def __get_pbp_table(self) -> _PlaceholderTable:
        # pbp table placeholder is the 7th on page
        placeholders = self.__soup.find_all("div", {"class": "placeholder"}, limit=7)
        ph = placeholders[-1]
        return _PlaceholderTable(ph)
    
    def __get_play_rows(self):
        return self.__pbp_table.find_all(
            "tr",
            id=lambda id: id and id.startswith("event_")
            )

class _GamePlayerQueryRunner:
    
    def __init__(self, player_tables: _PlayerTables):
        name_ids =  set(player_tables.home.get_name_ids())
        name_ids.update(player_tables.away.get_name_ids())
        self._name_ids = name_ids
        
    def add_game_players(self, game: Game) -> None:
        GamePlayer.insert_many(
            self.__get_rows(game),
            fields=[GamePlayer.game_id, GamePlayer.player_id]
            ).execute()

    def __get_rows(self, game: Game) -> Iterable[Tuple[int, int]]:
        for pid in Player.select(Player.id).where(Player.name_id.in_(self._name_ids)):
            yield (game.id, pid.id)
        
class _PlayDataTransformer:
    """Transforms data contained in play rows to data that is ready for
    insertion into the Play database table.
    """
    
    __INNING_CHAR_OFFSET = {
            "t": 0,
            "b": 1
        }
    
    # Home team gets to bat last, i.e. in second half of inning (b).
    __INNING_AND_PLAYER_TO_SIDE = {
        ("t", "batter") : "away",
        ("b", "batter") : "home",
        ("t", "pitcher"): "home",
        ("b", "pitcher"): "away",
    }
    
    # These instance methods can translate to db data with only raw data (arg)
    # as input.
    __RawStatTranslation = Callable[["_PlayDataTransformer", str     ], Any]
    
    # These instance methods require knowledge of inning half (2nd str arg) to 
    # determine if home or away player for id lookup.
    __PlayerLookup  = Callable[["_PlayDataTransformer", str, str], int]
    
    """
    THE FOLLOWING CLASS VARS ARE INSTANTIATED IN A CLASS METHOD AND NOT HERE.
    
    Each of the translation/lookup functions are not defined yet at this point,
    so they can't be instantiated here.
    """
    
    # Matches each raw stat name to its db stat name and translation function.
    __PBP_TO_DB_STATS: Dict[str, Tuple[str, __RawStatTranslation]]
    
    # Matches each player raw name_id to the db field for the player id, along
    # with the lookup function to translate name_id to player id.
    __PLAYERS:         Dict[str, Tuple[str, __PlayerLookup      ]]
    
    # "data-stat" names to extract from each player row.
    __PBP_STATS: Set[str]
    
    def __init__(self, player_tables: _PlayerTables):
        self.__init_lookups()
        self.__player_maps = {
            "home": player_tables.home.get_name_to_db_ids(),
            "away": player_tables.away.get_name_to_db_ids(),
        }
        
    @classmethod
    def __init_lookups(cls):
        """Initializes dicts to lookup database stat names and
        transformation functions to translate page data to database format.
        """
        if hasattr(cls, "PBP_TO_DB_STATS"):
            return
        
        cls.__PBP_TO_DB_STATS = {
            "inning":               ("inning_half"  , cls.__inning_to_inning_half),
            "pitches_pbp":          ("pitch_ct"     , cls.__strip),
            "play_desc":            ("desc"         , cls.__no_transformation_needed),
            "runners_on_bases_pbp": ("start_on_base", cls.__runners_to_on_base),
            "outs":                 ("start_outs"   , cls.__convert_to_int),
        }
        
        cls.__PLAYERS = {
            "batter":               ("batter_id"    , cls.__batter_to_id),
            "pitcher":              ("pitcher_id"   , cls.__pitcher_to_id),
        }
        cls.__PBP_STATS = set(cls.__PBP_TO_DB_STATS.keys()).union(set(cls.__PLAYERS.keys()))
        
    def extract_raw_play_data(self, play_row) -> Dict[str, str]:
        raw_play_data: Dict[str, str] = {}
        for play_data_pt in play_row.find_all():
            # each row (tr) has tags (th, td) with "data-stat" attributes; the
            # values of these attributes are the names of the contained stats
            data_stat = str(play_data_pt.get("data-stat"))
            if data_stat in self.__PBP_STATS:
                raw_play_data[data_stat] = play_data_pt.text.replace(u"\xa0", u" ")
        return raw_play_data
    
    def transform_raw_play_data(self, raw_play_data: Dict[str, str]) -> Dict[str, Any]:
        transformed_stats = self.__transform_stats(raw_play_data)
        self.__insert_player_ids(raw_play_data, into_dict=transformed_stats)
        return transformed_stats
    
    def __transform_stats(self, raw_play_data: Dict[str, str]) -> Dict[str, Any]:
        new_data: Dict[str, Any] = {}
        for pbp_statname, (db_statname, transform_func) in self.__PBP_TO_DB_STATS.items():
            new_data[db_statname] = transform_func(self, raw_play_data[pbp_statname])
        return new_data
    
    def __insert_player_ids(self, raw_play_data: Dict[str, str], into_dict: Dict[str, Any]) -> Dict[str, str]:
        inning_half_char = raw_play_data["inning"][0]
        for player_type, (player_type_id, player_lookup_func) in self.__PLAYERS.items():
            player_name = raw_play_data[player_type]
            into_dict[player_type_id] = player_lookup_func(self, player_name, inning_half_char)
        return into_dict
    
    def __inning_to_inning_half(self, inning: str) -> int:
        #[t|b][0-9]+ (t1, b2, t11, etc)
        inning_num = int(inning[1:])
        inning_half_char = inning[0]
        # 0-indexed (t1 -> 0; b1 -> 1; t2 -> 2 etc)
        return 2 * (inning_num - 1) + self.__INNING_CHAR_OFFSET[inning_half_char]
    
    def __runners_to_on_base(self, runners: str) -> int:
        #[-|1][-|2][-|3] where - means nobody on base (---, 1-3, 12-, etc)
        on_base = 0
        for base, on_base_flag in zip(runners, [OnBase.FIRST, OnBase.SECOND, OnBase.THIRD]):
            if not base == "-":
                on_base += on_base_flag.value
        return on_base
    
    def __batter_to_id(self, batter_name: str, inning_half_char: str) -> int:
        return self.__player_to_id(batter_name, inning_half_char, "batter")
    
    def __pitcher_to_id(self, pitcher_name: str, inning_half_char: str) -> int:
        return self.__player_to_id(pitcher_name, inning_half_char, "pitcher")
    
    def __player_to_id(self, player_name: str, inning_half_char: str, player_type: str) -> int:
        side = self.__INNING_AND_PLAYER_TO_SIDE[(inning_half_char, player_type)]
        pmap = self.__player_maps[side]
        try:
            # first try unedited name, since there's some overhead w/ stripping
            return pmap[player_name]
        except KeyError:
            stripped_name = _NameStripper.get_stripped_name(player_name)
            return pmap[stripped_name]
        
        # if all attempts fail, there's a new edge case that needs to be
        # considered
        raise KeyError(player_name)
        
    def __strip(self, stat: str) -> str:
        return stat.strip()
    
    def __no_transformation_needed(self, stat: str) -> str:
        return stat
    
    def __convert_to_int(self, stat: str) -> int:
        return int(stat)
