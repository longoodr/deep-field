from abc import ABC, abstractmethod
from typing import Iterable, Type

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
    
    @abstractmethod
    def _get_page_type(self) -> Type["Page"]:
        """Returns the type of page this link corresponds to."""
        pass
    
    def _get_name_id(self) -> str:
        """Returns a unique identifier for the corresponding page."""
        return self._url.split("/")[-1].split(".")[0]
    
    def __str__(self) -> str:
        return self._url
    
    def __hash__(self):
        if not hasattr(self, "_hash"):
            self._hash = hash(str(self._url))
        return self._hash
    
    def __eq__(self, other):
        return (self.__class__ == other.__class__ 
                and str(self._url) ==  str(other._url)    
            )

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
    
    def __hash__(self):
        if not hasattr(self, "_hash"):
            self._hash = hash(str(self._soup))
        return self._hash
    
    def __eq__(self, other) -> bool:
        return (self.__class__ == other.__class__ 
                and str(self._soup) == str(other._soup)    
            )
    
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
