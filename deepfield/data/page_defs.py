from abc import ABC, abstractmethod
from typing import Iterable

from bs4 import BeautifulSoup


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
