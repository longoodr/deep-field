from abc import ABC, abstractmethod
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup
from peewee import Query

from deepfield.data.dbmodels import Team, Venue
from deepfield.data.dependencies import DependencyResolver


class Page(ABC):
    """A collection of data located on an HTML page. A page may have
    dependencies on pages located at URLs. This induces a dependency DAG which
    can be traversed via DFS by a scraper. The page will refuse to insert its
    data unless all these dependencies are resolved by the given
    DependencyResolver.
    """
        
    def __init__(self, html: str, dep_res: DependencyResolver):
        self._soup = BeautifulSoup(html)
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
    """A page corresponding to the play-by-play info for a game."""
    
    def __init__(self, html: str, dep_res: DependencyResolver):
        super().__init__(html, dep_res)
        self._scorebox = self._soup.find("div", {"class": "scorebox"})
        self._scorebox_meta = self._scorebox.find("div", {"class": "scorebox_meta"})
    
    def _run_queries(self) -> None:
        # TODO: should add the teams, venue, game, contained plays in that order
        teams = self._add_teams()
        venue = self._add_venue()
    
    def _add_venue(self) -> Venue:
        name = self._get_venue_name()
        venue, _ = Venue.get_or_create(name=name)
        return venue
        
    def _get_venue_name(self) -> str:
        venue_div_filter = lambda div: div.text.startswith("Venue: ")
        venue_div = self._scorebox_meta.find(venue_div_filter)
        return venue_div.text.split(": ")[1] # "Venue: <venue name>"
    
    def _add_teams(self) -> Iterable[Team]:
        teams = []
        info = self._get_team_info()
        for name, abbreviation in info:
            team, _ = Team.get_or_create(name=name, abbreviation=abbreviation)
            teams.append(team)
        return teams
    
    def _get_team_info(self) -> Iterable[Tuple[str, str]]:
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
    
    def get_referenced_page_urls(self) -> Iterable[str]:
        return [] # TODO: should be player URLs
