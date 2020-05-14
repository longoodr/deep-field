import os
from abc import ABC, abstractmethod
from time import sleep
from time import time as get_cur_time
from typing import Dict, Iterable, Optional, Set, Tuple, Type

import requests
from requests.exceptions import HTTPError

from deepfield.data.page_defs import Page, InsertablePage
from deepfield.data.bbref_pages import (BBRefLink, BBRefPage, GamePage,
                                        PlayerPage, SchedulePage)
from deepfield.data.dbmodels import Game, Player
from pathlib import Path

    
class PageFactory:
    """Creates pages from links."""
    
    @staticmethod
    def create_page_from_url(url: str) -> Page:
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
    
class _HtmlRetriever(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link."""
    
    __HANDLER_SEQUENCE: Iterable[Type["_AbstractHtmlRetrievalHandler"]]
    
    def __init__(self, link: BBRefLink):
        super().__init__(link)
        self.__init_handler_seq()
        
    @classmethod
    def __init_handler_seq(cls) -> None:
        cls.__HANDLER_SEQUENCE = [
            _CachedHandler,
            _WebHandler
        ]
        
    def retrieve_html(self) -> Optional[str]:
        for handler_type in self.__HANDLER_SEQUENCE:
            html = handler_type(self._link).retrieve_html()
            if html is not None:
                return html
        return None
    
class _CachedHandler(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from local cache."""

    def retrieve_html(self) -> Optional[str]:
        return HtmlCache.get().find_html(self._link)
    
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

class _AbstractHtmlCache(ABC):
    """A cache containing HTML pages."""
    
    def __init__(self, root: str):
        self._root = root
        
    @abstractmethod
    def find_html(self, link: BBRefLink) -> Optional[str]:
        """Returns HTML if cache lookup successful, or None if not."""
        pass
    
    @abstractmethod
    def insert_html(self, html: str, link: BBRefLink) -> None:
        """Inserts the given HTML to the cache, with the name being determined
        by the given link.
        """
        pass
    
    def _full_path(self, rel_path: str) -> str:
        return os.path.join(self._root, rel_path)

    def _get_file_html(self, filename: str) -> str:
        with open(self._full_path(filename), 'r') as html_file:
            return html_file.read()

    @staticmethod
    def _get_filename(link: BBRefLink) -> str:
        """Gets the filename for the given link."""
        return link.name_id + ".shtml"
    
class HtmlCache(_AbstractHtmlCache):
    """A folder containing subfolders of HTML pages, each containing the HTML
    corresponding to the different types of pages.
    """
    
    _instance: "HtmlCache"
    
    @classmethod
    def get(cls) -> "HtmlCache":
        if not hasattr(cls, "_instance"):
            project_root = Path(__file__).parents[2] # data -> deepfield -> deep-field
            if "TESTING" in os.environ:
                root = (project_root / os.path.join("tests", "data", "resources")).resolve()
            else:
                root = (project_root / os.path.join("deepfield", "data", "pages")).resolve()
            cls._instance = HtmlCache(str(root))
        return cls._instance
    
    __PAGE_TYPES = [
        GamePage,
        PlayerPage,
        SchedulePage
    ]
    
    def __init__(self, root: str):
        """DO NOT CALL THIS EXTERNALLY!!! Use get() instead."""
        super().__init__(root)
        self.__caches: Dict[Type[BBRefPage], _AbstractHtmlCache] = {}
        for page_type in self.__PAGE_TYPES:
            cache_root = self._full_path(page_type.__name__)
            self.__caches[page_type.__name__] = _HtmlFolder(cache_root)
    
    def find_html(self, link: BBRefLink) -> Optional[str]:
        page_type = link.page_type.__name__
        return self.__caches[page_type].find_html(link)
    
    def insert_html(self, html: str, link: BBRefLink) -> None:
        if not os.path.isdir(self._root):
            os.mkdir(self._root)
        page_type = link.page_type.__name__
        self.__caches[page_type].insert_html(html, link)

class _HtmlFolder(_AbstractHtmlCache):
    """A folder containing HTML pages."""
    
    def find_html(self, link: BBRefLink) -> Optional[str]:
        if not os.path.isdir(self._root):
            return None
        
        # XXX O(n) lookup time; consider caching contents in set
        # (How to handle set updating efficiently? Recreation from scratch
        # would be SLOW but that's what os.listdir() forces)
        for f in os.listdir(self._root):
            if self._get_filename(link) == f:
                return self._get_file_html(f)
        return None
    
    def insert_html(self, html: str, link: BBRefLink) -> None:
        if not os.path.isdir(self._root):
            os.mkdir(self._root)
        with open(self._get_filename(link), 'w') as html_file:
            html_file.write(html)
