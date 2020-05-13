from typing import Type

from deepfield.data.bbref_pages import (BBRefLink, BBRefPage, GamePage,
                                        PlayerPage, SchedulePage)
from deepfield.data.dbmodels import Game, Player


class BBRefPageFactory:
    """Creates BBRefPages from BBRefLinks."""
    
    def create_page_from_link(self, link: BBRefLink) -> BBRefPage:
        page_type = self.__get_link_page_type(link)
        html = HTMLRetriever(link).retrieve_html()
        return page_type(html)
    
    @classmethod
    def __get_link_page_type(cls, link: BBRefLink) -> Type[BBRefPage]:
        if "boxes" in link._url:
            return GamePage
        elif "players" in link._url:
            return PlayerPage
        elif "schedule" in link._url:
            return SchedulePage
        raise ValueError(f"Couldn't determine page type of {link}")
    
class HTMLRetriever:
    """Retrieves HTML associated with the given link."""
    
    def __init__(self, link: BBRefLink):
        self._link = link
        
    def retrieve_html(self) -> str:
        raise NotImplementedError