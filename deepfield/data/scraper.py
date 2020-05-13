from abc import ABC, abstractmethod
from typing import Iterable, Optional, Type

from deepfield.data.bbref_pages import (BBRefLink, BBRefPage, GamePage,
                                        PlayerPage, SchedulePage)
from deepfield.data.dbmodels import Game, Player


class BBRefPageFactory:
    """Creates BBRefPages from BBRefLinks."""
    
    def create_page_from_link(self, link: BBRefLink) -> BBRefPage:
        html = HtmlRetriever(link).retrieve_html()
        if html is None:
            raise ValueError(f"Could not get HTML for {link}")
        return link.page_type(html)
    
class AbstractHtmlRetrievalHandler(ABC):
    """A step in the HTML retrieval process."""
    
    def __init__(self, link: BBRefLink):
        self._link = link
    
    @abstractmethod
    def retrieve_html(self) -> Optional[str]:
        """Returns HTML if successful, or None if not."""
        pass
 
class CachedHandler(AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from local cache."""

    def retrieve_html(self) -> Optional[str]:
        raise NotImplementedError
    
class WebHandler(AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from the web."""
    
    def retrieve_html(self) -> Optional[str]:
        raise NotImplementedError
    
class HtmlRetriever(AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link."""
    
    __HANDLER_SEQUENCE = [
        CachedHandler,
        WebHandler
    ]
    
    def __init__(self, link: BBRefLink):
        super().__init__(link)
        
    def retrieve_html(self) -> Optional[str]:
        for handler_type in self.__HANDLER_SEQUENCE:
            html = handler_type(self._link).retrieve_html()
            if html is not None:
                return html
        return None