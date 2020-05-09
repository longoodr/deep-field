from abc import ABC, abstractmethod
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from deepfield.data.dbmodels import DeepFieldModel
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
        for model in self._get_models_to_add():
            model.save()
        
    @abstractmethod
    def _get_models_to_add(self) -> Iterable[DeepFieldModel]:
        """Enumerates all models that exist on the page that need to be 
        inserted into the database.
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
    
    def _get_models_to_add(self) -> Iterable[DeepFieldModel]:
        return []
    
    def get_referenced_page_urls(self) -> Iterable[str]:
        urls = []
        games = self._soup.find_all("p", {"class": "game"})
        for game in games:
            suffix = game.em.a["href"]
            urls.append(self.base_url + suffix)
        return urls
