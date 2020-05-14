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
        html = _HtmlRetriever(link).retrieve_html()
        if html is None:
            raise ValueError(f"Could not get HTML for {link}")
        return link.page_type(html)
    
class _AbstractHtmlRetrievalHandler(ABC):
    """A step in the HTML retrieval process."""
    
    def __init__(self, link: BBRefLink):
        self._link = link
    
    @abstractmethod
    def retrieve_html(self) -> Optional[str]:
        """Returns HTML if successful, or None if not."""
        pass

class _CachedHandler(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from local cache."""

    """
    TODO
    1. Determine cache location based on TESTING environment variable.
    
    2. Lazy load cache directories: if they don't exist, then only create
        them whenever a page needs to be inserted into it.
        
        Structure:
            cache
            |__GamePage
            |__PlayerPage
            |__SchedulePage
    
    3. Make WebHandlers insert their scraped pages into the cache.
    """

    def retrieve_html(self) -> Optional[str]:
        """TODO Look up link in cache subfolder depending on link type. Return
        None if not found or if any folders do not exist.
        """
        return None
    
class _WebHandler(_AbstractHtmlRetrievalHandler):
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
    
class _HtmlRetriever(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link."""
    
    __HANDLER_SEQUENCE = [
        _CachedHandler,
        _WebHandler
    ]
    
    def __init__(self, link: BBRefLink):
        super().__init__(link)
        
    def retrieve_html(self) -> Optional[str]:
        for handler_type in self.__HANDLER_SEQUENCE:
            html = handler_type(self._link).retrieve_html()
            if html is not None:
                return html
        return None
