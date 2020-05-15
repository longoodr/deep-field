import os
from abc import ABC, abstractmethod
from pathlib import Path
from time import sleep
from time import time as get_cur_time
from typing import Callable, Dict, Iterable, Optional, Type

import requests
from bs4 import BeautifulSoup


class Link(ABC):
    """A page located at a URL that can determine if itself already exists in 
    the database or not.
    """
    
    def __init__(self, url: str):
        self._url = url
        self.name_id = self._get_name_id()
        self.page_type = self._get_page_type()
    
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
    
    @staticmethod
    def from_link(link: Link, cachable: bool = True) -> "Page":
        html = _HtmlRetriever(link, cachable).retrieve_html()
        if html is None:
            raise ValueError(f"Could not get HTML for {link}")
        return link.page_type(html)
     
    def __init__(self, html: str):
        self._soup = BeautifulSoup(html, "lxml")
    
    @abstractmethod
    def get_links(self) -> Iterable[Link]:
        """Enumerates all referenced links on this page."""
        pass
    
    @abstractmethod
    def __str__(self) -> str:
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
    
    Handler = Callable[["_HtmlRetriever"], Optional[str]]
    _HANDLER_SEQUENCE: Iterable[Handler]
    
    def __init__(self, link: Link, cachable: bool = True):
        super().__init__(link)
        self.__init_handler_seq()
        self._cachable = cachable
        
    @classmethod
    def __init_handler_seq(cls) -> None:
        if not hasattr(cls, "_HANDLER_SEQUENCE"):
            cls._HANDLER_SEQUENCE = [
                cls._run_cached_handler,
                cls._run_web_handler
            ]
        
    def retrieve_html(self) -> Optional[str]:
        for handler in self._HANDLER_SEQUENCE:
            html = handler(self)
            if html is not None:
                return html
        return None
    
    def _run_cached_handler(self) -> Optional[str]:
        if self._cachable:
            return _CachedHandler(self._link).retrieve_html()
        return None
    
    def _run_web_handler(self) -> Optional[str]:
        return _WebHandler(self._link, self._cachable).retrieve_html()
    
    
class _CachedHandler(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from local cache."""

    def retrieve_html(self) -> Optional[str]:
        return HtmlCache.get().find_html(self._link)
    
class _WebHandler(_AbstractHtmlRetrievalHandler):
    """Retrieves HTML associated with the given link from the web."""
    
    def __init__(self, link: Link, cache_insert: bool = True):
        super().__init__(link)
        self.__insert = cache_insert
    
    # baseball-reference.com's robots.txt specifies a crawl delay of 3 seconds
    __CRAWL_DELAY = 3
    __last_pull_time = 0.0
    
    def retrieve_html(self) -> Optional[str]:
        self.__wait_until_can_pull()
        self.__set_last_pull_time()
        response = requests.get(str(self._link))
        response.raise_for_status()
        html = response.text
        if self.__insert:
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
            # ensure in right spot: data -> deepfield -> deep-field
            parents = Path(__file__).parents
            for actual, expected in zip(parents, ["data", "deepfield", "deep-field"]):
                if actual.name != expected:
                    raise RuntimeError("HtmlCache def not found with right parent folder structure")
            project_root = parents[2]
            if "TESTING" in os.environ:
                root = (project_root / os.path.join("tests", "data", "resources")).resolve()
            else:
                root = (project_root / os.path.join("deepfield", "data", "pages")).resolve()
            cls._instance = HtmlCache(str(root))
        return cls._instance
    
    __PAGE_TYPES = [
        "GamePage",
        "PlayerPage",
        "SchedulePage"
    ]
    
    def __init__(self, root: str):
        """DO NOT CALL THIS EXTERNALLY!!! Use get() instead."""
        super().__init__(root)
        self.__caches: Dict[str, _AbstractHtmlCache] = {}
        for page_type in self.__PAGE_TYPES:
            cache_root = self._full_path(page_type)
            self.__caches[page_type] = _HtmlFolder(cache_root)
    
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
    
    def find_html(self, link: Link) -> Optional[str]:
        if not os.path.isdir(self._root):
            return None
        if not hasattr(self, "_contained_files"):
            self.__init_contained_files()
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

    def __init_contained_files(self) -> None:
        contained_files = [f for f in os.listdir(self._root)
                           if os.path.isfile(self._full_path(f))]
        self._contained_files = set(contained_files)