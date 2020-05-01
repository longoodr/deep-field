from abc import ABC, abstractmethod
from typing import Iterable

from bs4 import BeautifulSoup

from deepfield.data.dbmodels import DeepFieldModel

class Page(ABC):
    """A collection of data contained in an HTML document that can be added
    into the database.
    """
        
    def __init__(self, html: str):
        self._soup = BeautifulSoup(html)
    
    def update_db(self) -> None:
        """Inserts all models on this page into the database. This method
        requires all dependent pages to already exist in the database.
        """
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

class SchedulePage(ABC):
    """A page containing a set of URLs corresponding to game pages."""
    pass