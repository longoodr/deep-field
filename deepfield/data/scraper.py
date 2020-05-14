from abc import ABC, abstractmethod
from time import sleep
from time import time as get_cur_time
from typing import Iterable, Optional, Type

import requests
from requests.exceptions import HTTPError

from deepfield.data.bbref_pages import (BBRefLink, BBRefPage, GamePage,
                                        PlayerPage, SchedulePage)
from deepfield.data.dbmodels import Game, Player


class BBRefPageFactory:
    """Creates BBRefPages from BBRefLinks."""
    
    def create_page_from_url(self, url: str) -> BBRefPage:
        link = BBRefLink(url)
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
        return None
    
class WebHandler(AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from the web."""
    
    # baseball-reference.com's robots.txt specifies a crawl delay of 3 seconds
    __CRAWL_DELAY = 3
    __last_pull_time = 0.0
    
    def retrieve_html(self) -> Optional[str]:
        self.__wait_until_can_pull()
        self.__set_last_pull_time()
        response = requests.get(str(self._link))
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return None
        return response.text
    
    def __wait_until_can_pull(self) -> None:
        t = get_cur_time()
        if self.__last_pull_time <= t - self.__CRAWL_DELAY:
            return
        secs_to_wait = max(0, self.__last_pull_time + self.__CRAWL_DELAY - t)
        sleep(secs_to_wait)
        
    @classmethod
    def __set_last_pull_time(cls):
        cls.__last_pull_time = get_cur_time()
    
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
