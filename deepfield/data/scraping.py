import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from time import sleep
from time import time as get_cur_time
from typing import Dict, Iterable, Optional, Set, Tuple, Type

import requests
from requests.exceptions import HTTPError

from deepfield.data.bbref_pages import (BBRefPage, GamePage, PlayerPage,
                                        SchedulePage)
from deepfield.data.dbmodels import Game, Player
from deepfield.data.page_defs import InsertablePage, Link, Page

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ScrapeNode:
    """A node in the page dependency graph. The nodes are traversed via DFS."""
    
    _cached_nodes: Dict[Page, "ScrapeNode"] = {}
    
    @classmethod
    def from_page(cls, page: Page):
        """Factory method to create proper ScrapeNode subclass from page. Use
        this over the constructor.
        """
        if page in cls._cached_nodes:
            return cls._cached_nodes[page]
        new_node: ScrapeNode
        if isinstance(page, InsertablePage):
            new_node = InsertableScrapeNode(page)
        else:
            new_node = ScrapeNode(page)
        cls._cached_nodes[page] = new_node
        return new_node
    
    def __init__(self, page: Page):
        self._page = page

    def scrape(self) -> int:
        """Scrapes the page corresponding to this node. Returns the total
        number of pages that were scraped during the process.
        """
        logger.info(f"Starting scrape for {self._page}")
        num_scraped = self._visit_children()
        logger.info(f"Finished scraping {self._page}")
        return num_scraped + 1
        
    def _visit_children(self) -> int:
        num_scraped = 0
        for link in self._page.get_links():
            if link.exists_in_db():
                continue
            page = PageFactory.create_page_from_link(link)
            num_scraped += ScrapeNode.from_page(page).scrape()
        return num_scraped
            
class InsertableScrapeNode(ScrapeNode):
    """A node in the page dependency graph that performs database insertion
    once all its children have been visited.
    """
    
    def __init__(self, page: InsertablePage):
        self._page = page
        
    def scrape(self) -> int:
        logger.info(f"Starting scrape for {self._page}")
        num_scraped = self._visit_children()
        self._page.update_db()
        logger.info(f"Finished scraping {self._page}")
        return num_scraped + 1

class PageFactory:
    """Creates pages from links."""
    
    @staticmethod
    def create_page_from_link(link: Link) -> Page:
        html = _HtmlRetriever(link).retrieve_html()
        if html is None:
            raise ValueError(f"Could not get HTML for {link}")
        return link.page_type(html)
    
class _AbstractHtmlRetrievalHandler(ABC):
    """A step in the HTML retrieval process."""
    
    def __init__(self, link: Link):
        self._link = link
    
    @abstractmethod
    def retrieve_html(self) -> Optional[str]:
        """Returns HTML if successful, or None if not."""
        pass
    
class _HtmlRetriever(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link."""
    
    __HANDLER_SEQUENCE: Iterable[Type["_AbstractHtmlRetrievalHandler"]]
    
    def __init__(self, link: Link):
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
        response.raise_for_status()
        html = response.text
        HtmlCache.get().insert_html(html, self._link)
        return html
    
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
    def find_html(self, link: Link) -> Optional[str]:
        """Returns HTML if cache lookup successful, or None if not."""
        pass
    
    @abstractmethod
    def insert_html(self, html: str, link: Link) -> None:
        """Inserts the given HTML to the cache, with the name being determined
        by the given link.
        """
        pass
    
    def _full_path(self, rel_path: str) -> str:
        return os.path.join(self._root, rel_path)

    def _get_file_html(self, filename: str) -> str:
        with open(self._full_path(filename), 'r', encoding="utf-8") as html_file:
            return html_file.read()

    @staticmethod
    def _get_filename(link: Link) -> str:
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
    
    def find_html(self, link: Link) -> Optional[str]:
        page_type = link.page_type.__name__
        return self.__caches[page_type].find_html(link)
    
    def insert_html(self, html: str, link: Link) -> None:
        if not os.path.isdir(self._root):
            os.mkdir(self._root)
        page_type = link.page_type.__name__
        self.__caches[page_type].insert_html(html, link)

class _HtmlFolder(_AbstractHtmlCache):
    """A folder containing HTML pages."""
    
    def __init__(self, root: str):
        super().__init__(root)
        contained_files = [f for f in os.listdir(self._root)
                           if os.path.isfile(self._full_path(f))]
        self._contained_files = set(contained_files)
    
    def find_html(self, link: Link) -> Optional[str]:
        if not os.path.isdir(self._root):
            return None
        filename = self._get_filename(link)
        if filename in self._contained_files:
            return self._get_file_html(filename)
        return None
    
    def insert_html(self, html: str, link: Link) -> None:
        if not os.path.isdir(self._root):
            os.mkdir(self._root)
        filename = self._get_filename(link)
        filepath = self._full_path(filename)
        with open(filepath, 'w', encoding="utf-8") as html_file:
            html_file.write(html)
        self._contained_files.add(filename)
